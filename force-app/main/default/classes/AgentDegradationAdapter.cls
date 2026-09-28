/**
 * AgentDegradationAdapter.cls
 * Implements Post-Execution Gate shielding for AgentActionGateway:
 * 1. Exception Shielding: Intercepts raw unhandled Apex exceptions (DML, Limit, NullPointer)
 * 2. Contract Normalization: Produces clear, structured messages so the LLM never hallucinates.
 */
global with sharing class AgentDegradationAdapter {

    /**
     * Converts an unhandled Exception into a standardized, safe ActionResult.
     */
    public static AgentActionGateway.ActionResult handleException(String actionName, Exception ex) {
        AgentActionGateway.ActionResult res = new AgentActionGateway.ActionResult();
        res.isSuccess = false;
        res.actionName = actionName;

        String typeName = ex.getTypeName();

        if (typeName.contains('DmlException')) {
            res.errorCode = 'DML_TRANSACTION_FAILED';
            res.errorMessage = 'A database validation or lock issue occurred. Please ask the customer to confirm required fields.';
        } else if (typeName.contains('LimitException')) {
            res.errorCode = 'GOVERNOR_LIMIT_EXCEEDED';
            res.errorMessage = 'System resources were temporarily constrained. Please suggest trying again shortly.';
        } else if (typeName.contains('NullPointerException')) {
            res.errorCode = 'MISSING_REQUIRED_INPUT';
            res.errorMessage = 'Incomplete data provided for ' + actionName + '. Please verify the input values.';
        } else {
            res.errorCode = 'SYSTEM_ERROR';
            res.errorMessage = 'An error occurred while executing ' + actionName + ': ' + ex.getMessage();
        }

        return res;
    }

    /**
     * Creates a standardized failure result from a blocked gate decision.
     */
    public static AgentActionGateway.ActionResult handleBlocked(String actionName, String errorCode, String reason) {
        AgentActionGateway.ActionResult res = new AgentActionGateway.ActionResult();
        res.isSuccess = false;
        res.actionName = actionName;
        res.errorCode = errorCode;
        res.errorMessage = reason;
        return res;
    }
}
