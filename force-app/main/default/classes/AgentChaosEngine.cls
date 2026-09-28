/**
 * AgentChaosEngine.cls
 * Extensible, reusable runtime chaos engine for Salesforce Agentforce Invocable Actions.
 * Drop this class into your Salesforce Org to add fault injection to ANY native action.
 */
global with sharing class AgentChaosEngine {

    global static final String FAULT_NONE = 'NONE';
    global static final String FAULT_DML = 'DML_EXCEPTION';
    global static final String FAULT_CPU_TIMEOUT = 'CPU_TIMEOUT';
    global static final String FAULT_SOQL_LIMIT = 'SOQL_LIMIT';
    global static final String FAULT_MUTATED_DATA = 'MUTATED_DATA';

    global class EvaluationResult {
        global Boolean shouldInject;
        global String faultType;
        global String errorMessage;

        global EvaluationResult() {
            this.shouldInject = false;
            this.faultType = FAULT_NONE;
            this.errorMessage = '';
        }

        global void applyDelayIfConfigured(Integer delayMs) {
            if (delayMs != null && delayMs > 0) {
                Long start = System.currentTimeMillis();
                while (System.currentTimeMillis() - start < delayMs) {
                    // Spin to simulate CPU processing / long calculation
                }
            }
        }
    }

    /**
     * Parse chaos directives from input parameters, query strings, or metadata.
     * Checks for dynamic keywords in string fields (e.g. '[CHAOS_CPU]', 'chaos-dml@test.com').
     */
    global static EvaluationResult evaluate(String actionName, String rawDirective) {
        EvaluationResult res = new EvaluationResult();
        if (String.isBlank(rawDirective)) {
            return res;
        }

        String lower = rawDirective.toLowerCase();

        if (lower.contains('chaos-dml') || lower.contains('[chaos_dml]')) {
            res.shouldInject = true;
            res.faultType = FAULT_DML;
            res.errorMessage = 'DML Exception: FIELD_CUSTOM_VALIDATION_EXCEPTION, Validation rule failed for ' + actionName;
        } else if (lower.contains('chaos-timeout') || lower.contains('[chaos_cpu_timeout]')) {
            res.shouldInject = true;
            res.faultType = FAULT_CPU_TIMEOUT;
            res.errorMessage = 'Apex CPU time limit exceeded (10000ms) in ' + actionName;
            // Spin for 11 seconds to trigger governor limit or wall-clock drop
            res.applyDelayIfConfigured(11000);
        } else if (lower.contains('chaos-soql') || lower.contains('[chaos_soql]')) {
            res.shouldInject = true;
            res.faultType = FAULT_SOQL_LIMIT;
            res.errorMessage = 'System.LimitException: Too many SOQL queries: 101';
        } else if (lower.contains('chaos-corrupt') || lower.contains('[chaos_corrupt]')) {
            res.shouldInject = true;
            res.faultType = FAULT_MUTATED_DATA;
            res.errorMessage = 'Data mutation: required attributes missing or invalid';
        } else if (lower.contains('[chaos_delay_') && lower.contains('s]')) {
            // Support arbitrary delay: e.g. [CHAOS_DELAY_14S]
            Integer seconds = extractSeconds(lower);
            res.shouldInject = true;
            res.applyDelayIfConfigured(seconds * 1000);
        }

        return res;
    }

    private static Integer extractSeconds(String text) {
        try {
            Integer startIdx = text.indexOf('[chaos_delay_') + 13;
            Integer endIdx = text.indexOf('s]', startIdx);
            return Integer.valueOf(text.substring(startIdx, endIdx));
        } catch (Exception e) {
            return 5;
        }
    }
}
