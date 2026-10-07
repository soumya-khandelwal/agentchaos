/**
 * AgentGatePolicy.cls
 * Implements Pre-Execution Gate checks for AgentActionGateway:
 * 1. Loop Breaker / Rate Limiter (Protects governor limits against runaway ReAct loops)
 * 2. Active Declarative Chaos Fault Injector (Reads Agent_Chaos_Rule__mdt or mock rules)
 * 3. Directive Keyword Fallback (Evaluates prompt directives like [chaos_dml])
 */
global with sharing class AgentGatePolicy {

    // In-memory invocation counter across a single turn/transaction
    private static Map<String, Integer> actionCallCounts = new Map<String, Integer>();
    public static Integer MAX_CALLS_PER_TURN = 3;

    // Declarative Rule Model
    public class DeclarativeRule {
        public String actionName;
        public String faultType;
        public String errorMessage;
        public Integer delaySeconds;
        public Integer maxTriggerCount;
        public Boolean isActive;
    }

    // In-memory mock rules for unit tests or sandboxes without deployed metadata
    private static Map<String, DeclarativeRule> mockRules = new Map<String, DeclarativeRule>();

    public class GateDecision {
        public Boolean isAllowed;
        public String blockedReason;
        public String errorCode;
    }

    /**
     * Set a mock declarative rule (useful for unit tests and local simulations).
     */
    public static void setMockRule(String actionName, String faultType, String errorMsg, Integer delaySec) {
        DeclarativeRule rule = new DeclarativeRule();
        rule.actionName = actionName;
        rule.faultType = faultType;
        rule.errorMessage = errorMsg;
        rule.delaySeconds = delaySec != null ? delaySec : 0;
        rule.isActive = true;
        mockRules.put(actionName, rule);
    }

    /**
     * Clear mock declarative rules.
     */
    public static void clearMockRules() {
        mockRules.clear();
    }

    /**
     * Resets invocation counters (useful for unit tests or starting new turns).
     */
    public static void resetCounters() {
        actionCallCounts.clear();
    }

    /**
     * Evaluates all pre-execution gate rules for an incoming action request.
     */
    public static GateDecision evaluatePreExecution(String actionName, String directive) {
        GateDecision decision = new GateDecision();
        decision.isAllowed = true;

        // Gate Rule 1: Loop Breaker / Runaway ReAct Protection
        Integer currentCount = actionCallCounts.containsKey(actionName) ? actionCallCounts.get(actionName) : 0;
        currentCount++;
        actionCallCounts.put(actionName, currentCount);

        if (currentCount > MAX_CALLS_PER_TURN) {
            decision.isAllowed = false;
            decision.errorCode = 'LOOP_BREAKER_TRIGGERED';
            decision.blockedReason = 'Circuit breaker tripped: Action [' + actionName + 
                '] called ' + currentCount + ' times in a single turn. Please ask the user for clarification instead of repeating this tool call.';
            return decision;
        }

        // Gate Rule 2: Declarative Metadata Chaos Rule Check
        DeclarativeRule activeRule = getActiveDeclarativeRule(actionName);
        if (activeRule != null && activeRule.isActive) {
            decision.isAllowed = false;
            decision.errorCode = 'CHAOS_FAULT_INJECTED';
            decision.blockedReason = String.isNotBlank(activeRule.errorMessage) 
                ? activeRule.errorMessage 
                : 'Declarative chaos fault [' + activeRule.faultType + '] triggered for action ' + actionName;
            
            if (activeRule.delaySeconds != null && activeRule.delaySeconds > 0) {
                Long start = System.currentTimeMillis();
                while (System.currentTimeMillis() - start < (activeRule.delaySeconds * 1000)) {
                    // Artificial delay spin
                }
            }
            return decision;
        }

        // Gate Rule 3: Directive Keyword Fallback Evaluation
        if (String.isNotBlank(directive)) {
            AgentChaosEngine.EvaluationResult chaos = AgentChaosEngine.evaluate(actionName, directive);
            if (chaos.shouldInject) {
                decision.isAllowed = false;
                decision.errorCode = 'CHAOS_FAULT_INJECTED';
                decision.blockedReason = chaos.errorMessage;
                return decision;
            }
        }

        return decision;
    }

    /**
     * Retrieve active declarative rule for action, prioritizing mock rules then SOQL metadata.
     */
    private static DeclarativeRule getActiveDeclarativeRule(String actionName) {
        // 1. Check in-memory mocks
        if (mockRules.containsKey(actionName)) {
            return mockRules.get(actionName);
        }
        if (mockRules.containsKey('*')) {
            return mockRules.get('*');
        }

        // 2. Query Custom Metadata Type if in a Salesforce runtime with metadata
        try {
            List<SObject> records = Database.query(
                'SELECT Action_Name__c, Fault_Type__c, Error_Message__c, Delay_Seconds__c, Is_Active__c ' +
                'FROM Agent_Chaos_Rule__mdt ' +
                'WHERE Is_Active__c = true AND (Action_Name__c = :actionName OR Action_Name__c = \'*\') ' +
                'LIMIT 1'
            );
            if (!records.isEmpty()) {
                SObject record = records[0];
                DeclarativeRule rule = new DeclarativeRule();
                rule.actionName = (String) record.get('Action_Name__c');
                rule.faultType = (String) record.get('Fault_Type__c');
                rule.errorMessage = (String) record.get('Error_Message__c');
                Decimal delay = (Decimal) record.get('Delay_Seconds__c');
                rule.delaySeconds = delay != null ? delay.intValue() : 0;
                rule.isActive = (Boolean) record.get('Is_Active__c');
                return rule;
            }
        } catch (Exception e) {
            // In test contexts where Custom Metadata is not deployed, silently continue
        }

        return null;
    }
}
