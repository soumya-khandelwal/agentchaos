/**
 * AgentActionGatewayTest.cls
 * Comprehensive unit test suite for AgentActionGateway, Gate Policies, and CaseSupportHandler.
 */
@IsTest
private class AgentActionGatewayTest {

    @IsTest
    static void testHappyPathCaseCreation() {
        AgentGatePolicy.resetCounters();

        AgentActionGateway.ActionRequest req = new AgentActionGateway.ActionRequest();
        req.actionName = 'createSupportCase';
        req.subject = 'Test Gateway Subject';
        req.customerEmail = 'clean-customer@example.com';
        req.priority = 'High';

        Test.startTest();
        List<AgentActionGateway.ActionResult> results = AgentActionGateway.execute(
            new List<AgentActionGateway.ActionRequest>{ req }
        );
        Test.stopTest();

        System.assertEquals(1, results.size(), 'Should return 1 result');
        AgentActionGateway.ActionResult res = results[0];
        System.assertEquals(true, res.isSuccess, 'Action should succeed on happy path');
        System.assertNotEquals(null, res.entityId, 'Entity ID should be populated');
        System.assertNotEquals(null, res.entityNumber, 'Entity Number should be populated');
        System.assert(res.outputMessage.contains('successfully created'), 'Output message should confirm creation');
    }

    @IsTest
    static void testChaosFaultInjectionBlocked() {
        AgentGatePolicy.resetCounters();

        AgentActionGateway.ActionRequest req = new AgentActionGateway.ActionRequest();
        req.actionName = 'createSupportCase';
        req.subject = 'Test Fault Injection';
        req.customerEmail = 'chaos-dml@test.com';
        req.chaosDirective = '[CHAOS_DML]';

        Test.startTest();
        List<AgentActionGateway.ActionResult> results = AgentActionGateway.execute(
            new List<AgentActionGateway.ActionRequest>{ req }
        );
        Test.stopTest();

        System.assertEquals(1, results.size(), 'Should return 1 result');
        AgentActionGateway.ActionResult res = results[0];
        System.assertEquals(false, res.isSuccess, 'Action should be blocked by chaos injection');
        System.assertEquals('CHAOS_FAULT_INJECTED', res.errorCode, 'Should return chaos error code');
        System.assert(res.errorMessage.contains('FIELD_CUSTOM_VALIDATION_EXCEPTION'), 'Error message should reflect DML block');
    }

    @IsTest
    static void testLoopBreakerTripping() {
        AgentGatePolicy.resetCounters();

        AgentActionGateway.ActionRequest req = new AgentActionGateway.ActionRequest();
        req.actionName = 'createSupportCase';
        req.subject = 'Loop Breaker Test';
        req.customerEmail = 'loop@example.com';

        Test.startTest();
        // Fire 4 consecutive calls to trigger loop breaker (> 3)
        AgentActionGateway.execute(new List<AgentActionGateway.ActionRequest>{ req });
        AgentActionGateway.execute(new List<AgentActionGateway.ActionRequest>{ req });
        AgentActionGateway.execute(new List<AgentActionGateway.ActionRequest>{ req });
        List<AgentActionGateway.ActionResult> results4 = AgentActionGateway.execute(
            new List<AgentActionGateway.ActionRequest>{ req }
        );
        Test.stopTest();

        System.assertEquals(1, results4.size());
        AgentActionGateway.ActionResult res4 = results4[0];
        System.assertEquals(false, res4.isSuccess, 'Fourth call should trip the loop breaker');
        System.assertEquals('LOOP_BREAKER_TRIGGERED', res4.errorCode);
        System.assert(res4.errorMessage.contains('Circuit breaker tripped'), 'Error message should warn about runaway loop');
    }

    @IsTest
    static void testUnknownActionHandling() {
        AgentGatePolicy.resetCounters();

        AgentActionGateway.ActionRequest req = new AgentActionGateway.ActionRequest();
        req.actionName = 'nonExistentAction';

        Test.startTest();
        List<AgentActionGateway.ActionResult> results = AgentActionGateway.execute(
            new List<AgentActionGateway.ActionRequest>{ req }
        );
        Test.stopTest();

        System.assertEquals(1, results.size());
        System.assertEquals(false, results[0].isSuccess);
        System.assertEquals('UNKNOWN_ACTION', results[0].errorCode);
    }
}
