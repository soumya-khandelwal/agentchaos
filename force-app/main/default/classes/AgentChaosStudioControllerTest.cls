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
}
