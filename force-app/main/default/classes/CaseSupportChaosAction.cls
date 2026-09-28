/**
 * CaseSupportChaosAction.cls
 * Production-ready Case Management Invocable Action for Agentforce.
 * Demonstrates how to use AgentChaosEngine to add fault injection to Case operations.
 */
global with sharing class CaseSupportChaosAction {

    global class Request {
        @InvocableVariable(required=true description='Subject of the customer case')
        global String subject;

        @InvocableVariable(required=true description='Customer email address')
        global String customerEmail;

        @InvocableVariable(description='Case Priority: Low, Medium, High')
        global String priority;

        @InvocableVariable(description='Optional chaos directive: [CHAOS_DML], [CHAOS_CPU_TIMEOUT], [CHAOS_DELAY_14S]')
        global String chaosDirective;
    }

    global class Result {
        @InvocableVariable(description='Whether the case creation succeeded')
        global Boolean isSuccess;

        @InvocableVariable(description='Created Case ID if successful')
        global String caseId;

        @InvocableVariable(description='Created 8-digit Case Number if successful')
        global String caseNumber;

        @InvocableVariable(description='Error message if operation failed')
        global String errorMessage;
    }

    @InvocableMethod(
        label='Create Support Case (AgentChaos Enabled)'
        description='Creates a customer case with pluggable chaos testing hooks for Agentforce'
    )
    global static List<Result> createSupportCase(List<Request> requests) {
        List<Result> results = new List<Result>();

        for (Request req : requests) {
            Result res = new Result();

            // Evaluate chaos from directive or input fields
            String directive = String.isNotBlank(req.chaosDirective) 
                ? req.chaosDirective 
                : (req.customerEmail + ' ' + req.subject);

            AgentChaosEngine.EvaluationResult chaos = AgentChaosEngine.evaluate('createSupportCase', directive);

            if (chaos.shouldInject) {
                res.isSuccess = false;
                res.errorMessage = chaos.errorMessage;
                results.add(res);
                continue;
            }

            try {
                Case newCase = new Case(
                    Subject = req.subject,
                    SuppliedEmail = req.customerEmail,
                    Priority = String.isNotBlank(req.priority) ? req.priority : 'Medium',
                    Status = 'New',
                    Origin = 'Agentforce'
                );
                insert newCase;

                Case created = [SELECT Id, CaseNumber FROM Case WHERE Id = :newCase.Id LIMIT 1];
                res.isSuccess = true;
                res.caseId = created.Id;
                res.caseNumber = created.CaseNumber;
            } catch (Exception ex) {
                res.isSuccess = false;
                res.errorMessage = ex.getMessage();
            }

            results.add(res);
        }
        return results;
    }
}
