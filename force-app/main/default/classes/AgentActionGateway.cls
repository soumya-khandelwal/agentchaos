/**
 * AgentActionGateway.cls
 * Centralized In-Flight Interceptor & Dynamic Dispatcher for Agentforce Actions.
 * Enforces:
 *   Gate 1: Pre-Execution (Loop Breaker, Chaos Fault Injection, Rate Limiter)
 *   Gate 2: Dynamic Handler Dispatch (IAgentActionHandler registry)
 *   Gate 3: Post-Execution (Graceful Degradation Adapter, Exception Shielding)
 */
global with sharing class AgentActionGateway {

    private static Map<String, IAgentActionHandler> registry = new Map<String, IAgentActionHandler>();

    static {
        // Register default business handlers
        registerHandler(new CaseSupportHandler());
    }

    /**
     * Registers a new action handler dynamically.
     */
    global static void registerHandler(IAgentActionHandler handler) {
        if (handler != null && String.isNotBlank(handler.getActionName())) {
            registry.put(handler.getActionName().toLowerCase(), handler);
        }
    }

    global class ActionRequest {
        @InvocableVariable(description='Target action name, e.g. createSupportCase')
        global String actionName;

        @InvocableVariable(description='Subject of the customer request')
        global String subject;

        @InvocableVariable(description='Customer email address')
        global String customerEmail;

        @InvocableVariable(description='Priority: Low, Medium, High')
        global String priority;

        @InvocableVariable(description='Optional JSON-encoded parameter payload')
        global String payloadJson;

        @InvocableVariable(description='Optional chaos directive: [CHAOS_DML], [CHAOS_CPU_TIMEOUT], [CHAOS_DELAY_14S]')
        global String chaosDirective;
    }

    global class ActionResult {
        @InvocableVariable(description='Whether the action succeeded')
        global Boolean isSuccess;

        @InvocableVariable(description='Action name executed')
        global String actionName;

        @InvocableVariable(description='Created Entity ID if applicable')
        global String entityId;

        @InvocableVariable(description='Created Entity Number (e.g. Case Number) if applicable')
        global String entityNumber;

        @InvocableVariable(description='User-friendly output message')
        global String outputMessage;

        @InvocableVariable(description='Error code if failed')
        global String errorCode;

        @InvocableVariable(description='Error message if failed')
        global String errorMessage;
    }

    @InvocableMethod(
        label='Agent Action Gateway (AgentChaos Interceptor)'
        description='Centralized in-flight interceptor and dynamic dispatcher for Agentforce actions'
    )
    global static List<ActionResult> execute(List<ActionRequest> requests) {
        List<ActionResult> results = new List<ActionResult>();

        for (ActionRequest req : requests) {
            String actionName = String.isNotBlank(req.actionName) ? req.actionName : 'createSupportCase';

            // Extract directive from chaosDirective field or email/subject
            String directive = String.isNotBlank(req.chaosDirective) 
                ? req.chaosDirective 
                : (req.customerEmail + ' ' + req.subject);

            // -------------------------------------------------------------
            // GATE 1: Pre-Execution Evaluation (Loop Breaker & Chaos Injection)
            // -------------------------------------------------------------
            AgentGatePolicy.GateDecision gate1 = AgentGatePolicy.evaluatePreExecution(actionName, directive);
            if (!gate1.isAllowed) {
                results.add(AgentDegradationAdapter.handleBlocked(actionName, gate1.errorCode, gate1.blockedReason));
                continue;
            }

            // -------------------------------------------------------------
            // GATE 2: Dynamic Handler Dispatch
            // -------------------------------------------------------------
            IAgentActionHandler handler = registry.get(actionName.toLowerCase());
            if (handler == null) {
                results.add(AgentDegradationAdapter.handleBlocked(
                    actionName, 
                    'UNKNOWN_ACTION', 
                    'No registered handler found for action: ' + actionName
                ));
                continue;
            }

            // Construct parameter map
            Map<String, Object> params = new Map<String, Object>();
            if (String.isNotBlank(req.payloadJson)) {
                try {
                    params = (Map<String, Object>) JSON.deserializeUntyped(req.payloadJson);
                } catch (Exception parseEx) {
                    // Fallback to explicit properties if JSON parsing fails
                }
            }
            if (String.isNotBlank(req.subject)) params.put('subject', req.subject);
            if (String.isNotBlank(req.customerEmail)) params.put('customerEmail', req.customerEmail);
            if (String.isNotBlank(req.priority)) params.put('priority', req.priority);

            // -------------------------------------------------------------
            // GATE 3: Execution & Post-Execution Shielding
            // -------------------------------------------------------------
            try {
                ActionResult res = handler.handle(params);
                results.add(res);
            } catch (Exception ex) {
                results.add(AgentDegradationAdapter.handleException(actionName, ex));
            }
        }

        return results;
    }
}
