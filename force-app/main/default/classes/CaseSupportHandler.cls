/**
 * CaseSupportHandler.cls
 * Production Case creation handler registered with AgentActionGateway.
 */
global with sharing class CaseSupportHandler implements IAgentActionHandler {

    global String getActionName() {
        return 'createSupportCase';
    }

    global AgentActionGateway.ActionResult handle(Map<String, Object> params) {
        AgentActionGateway.ActionResult res = new AgentActionGateway.ActionResult();
        res.actionName = getActionName();

        String subject = (String) params.get('subject');
        String customerEmail = (String) params.get('customerEmail');
        String priority = (String) params.get('priority');

        if (String.isBlank(subject) || String.isBlank(customerEmail)) {
            res.isSuccess = false;
            res.errorCode = 'VALIDATION_ERROR';
            res.errorMessage = 'Both subject and customerEmail are required to create a support case.';
            return res;
        }

        Case newCase = new Case(
            Subject = subject,
            SuppliedEmail = customerEmail,
            Priority = String.isNotBlank(priority) ? priority : 'Medium',
            Status = 'New',
            Origin = 'Agentforce'
        );
        insert newCase;

        Case created = [SELECT Id, CaseNumber FROM Case WHERE Id = :newCase.Id LIMIT 1];
        res.isSuccess = true;
        res.entityId = created.Id;
        res.entityNumber = created.CaseNumber;
        res.outputMessage = 'Support case successfully created with Case Number ' + created.CaseNumber + '.';
        return res;
    }
}
