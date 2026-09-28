/**
 * AgentGatePolicy.cls
 * Implements Pre-Execution Gate checks for AgentActionGateway:
 * 1. Loop Breaker / Rate Limiter (Protects governor limits against runaway ReAct loops)
 * 2. Active Chaos Fault Injector (Triggers CPU loops, DML blocks, artificial latency)
 */
global with sharing class AgentGatePolicy {

    // In-memory invocation counter across a single turn/transaction
    private static Map<String, Integer> actionCallCounts = new Map<String, Integer>();
    public static Integer MAX_CALLS_PER_TURN = 3;

    public class GateDecision {
        public Boolean isAllowed;
        public String blockedReason;
        public String errorCode;
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

        // Gate Rule 2: Chaos Fault Injection Evaluation
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
}
