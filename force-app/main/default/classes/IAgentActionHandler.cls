/**
 * IAgentActionHandler.cls
 * Standard pluggable interface for business actions routed through AgentActionGateway.
 */
global interface IAgentActionHandler {
    /**
     * Executes the business action with parameters unpacked from Agentforce.
     */
    AgentActionGateway.ActionResult handle(Map<String, Object> params);

    /**
     * Returns the unique action name (e.g. 'createSupportCase', 'trackOrder').
     */
    String getActionName();
}
