/**
 * AgentChaosStudioControllerTest.cls
 * Unit tests for AgentChaosStudioController.
 */
@isTest
private class AgentChaosStudioControllerTest {

    @isTest
    static void testGetAvailableActions() {
        Test.startTest();
        List<AgentChaosStudioController.ActionOptionDTO> actions = AgentChaosStudioController.getAvailableActions();
        Test.stopTest();

        Assert.isNotNull(actions, 'Actions list should not be null');
        Assert.isTrue(actions.size() >= 3, 'Should discover at least 3 default actions');
    }

    @isTest
    static void testGetActiveRules() {
        Test.startTest();
        List<AgentChaosStudioController.RuleItemDTO> rules = AgentChaosStudioController.getActiveRules();
        Test.stopTest();

        Assert.isNotNull(rules, 'Rules list should not be null');
        Assert.isTrue(rules.size() >= 1, 'Should include at least the hardcoded Gate 1 loop breaker rule');
    }

    @isTest
    static void testAuditActionExecution() {
        Test.startTest();
        AgentChaosStudioController.AuditReportDTO report = AgentChaosStudioController.auditAction('Create_Support_Case_Chaos');
        Test.stopTest();

        Assert.isNotNull(report, 'Audit report should not be null');
        Assert.areEqual('Create_Support_Case_Chaos', report.actionName);
        Assert.isTrue(report.isZeroCredit, 'Must be zero credit mode');
        Assert.areEqual(0, report.flexCreditsConsumed, 'Must consume 0 Flex Credits');
        Assert.areEqual(6, report.totalVectors, 'Must audit all 6 failure mode test vectors');
        Assert.isTrue(report.results.size() == 6, 'Must have 6 result items');
        Assert.isNotNull(report.overallScore, 'Overall score must be calculated');
    }

    @isTest
    static void testAuditActionWithBlankName() {
        Test.startTest();
        AgentChaosStudioController.AuditReportDTO report = AgentChaosStudioController.auditAction('');
        Test.stopTest();

        Assert.isNotNull(report);
        Assert.areEqual('Create_Support_Case_Chaos', report.actionName);
    }

    @isTest
    static void testGetAvailableAgents() {
        Test.startTest();
        List<AgentChaosStudioController.AgentOptionDTO> agents = AgentChaosStudioController.getAvailableAgents();
        Test.stopTest();

        Assert.isNotNull(agents);
        Assert.isTrue(!agents.isEmpty(), 'Should return at least one agent');
    }

    @isTest
    static void testSimulateAgentTurnVariants() {
        Test.startTest();
        // 1. Normal turn
        AgentChaosStudioController.AgentTurnResultDTO normalTurn = AgentChaosStudioController.simulateAgentTurn(
            'Customer_Support_Agent',
            'Hello, open a case for my parcel: customer@example.com'
        );
        Assert.isTrue(normalTurn.actionSucceeded);
        Assert.isTrue(normalTurn.isHallucinationClean);

        // 2. DML rollback chaos directive
        AgentChaosStudioController.AgentTurnResultDTO dmlTurn = AgentChaosStudioController.simulateAgentTurn(
            'Customer_Support_Agent',
            'I need to report another broken item. Email: chaos-dml@test.com'
        );
        Assert.isFalse(dmlTurn.actionSucceeded);
        Assert.isTrue(dmlTurn.isEscalatedToHuman);

        // 3. Timeout directive
        AgentChaosStudioController.AgentTurnResultDTO timeoutTurn = AgentChaosStudioController.simulateAgentTurn(
            'Customer_Support_Agent',
            'Package was delayed. [CHAOS_DELAY_14S]'
        );
        Assert.isFalse(timeoutTurn.slaCompliant);

        // 4. ReAct loop directive
        AgentChaosStudioController.AgentTurnResultDTO loopTurn = AgentChaosStudioController.simulateAgentTurn(
            'Customer_Support_Agent',
            'Keep retrying: retry-fail@test.com'
        );
        Assert.isTrue(loopTurn.isEscalatedToHuman);
        Test.stopTest();
    }
}
