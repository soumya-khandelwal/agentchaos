"""Extensible Apex Code Generator for Salesforce Agentforce Invocable Actions."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional


APEX_ENGINE_CLS = '''/**
 * AgentChaosEngine.cls
 * Extensible, reusable runtime chaos engine for Salesforce Agentforce Invocable Actions.
 * Drop this class into your Salesforce Org to add fault injection to ANY native action.
 */
public with sharing class AgentChaosEngine {

    public static final String FAULT_NONE = 'NONE';
    public static final String FAULT_DML = 'DML_EXCEPTION';
    public static final String FAULT_CPU_TIMEOUT = 'CPU_TIMEOUT';
    public static final String FAULT_SOQL_LIMIT = 'SOQL_LIMIT';
    public static final String FAULT_MUTATED_DATA = 'MUTATED_DATA';

    public class EvaluationResult {
        public Boolean shouldInject;
        public String faultType;
        public String errorMessage;

        public EvaluationResult() {
            this.shouldInject = false;
            this.faultType = FAULT_NONE;
            this.errorMessage = '';
        }

        public void applyDelayIfConfigured(Integer delayMs) {
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
    public static EvaluationResult evaluate(String actionName, String rawDirective) {
        EvaluationResult res = new EvaluationResult();
        if (String.isBlank(rawDirective)) {
            return res;
        }

        String lower = rawDirective.toLowerCase();

        if (lower.contains('chaos-dml') || lower.contains('[chaos_dml]')) {
            res.shouldInject = true;
            res.faultType = FaultType.DML_EXCEPTION;
            res.errorMessage = 'DML Exception: FIELD_CUSTOM_VALIDATION_EXCEPTION, Validation rule failed for ' + actionName;
        } else if (lower.contains('chaos-timeout') || lower.contains('[chaos_cpu_timeout]')) {
            res.shouldInject = true;
            res.faultType = FaultType.CPU_TIMEOUT;
            res.errorMessage = 'Apex CPU time limit exceeded (10000ms) in ' + actionName;
            // Spin for 11 seconds to trigger governor limit or wall-clock drop
            res.applyDelayIfConfigured(11000);
        } else if (lower.contains('chaos-soql') || lower.contains('[chaos_soql]')) {
            res.shouldInject = true;
            res.faultType = FaultType.SOQL_LIMIT;
            res.errorMessage = 'System.LimitException: Too many SOQL queries: 101';
        } else if (lower.contains('chaos-corrupt') || lower.contains('[chaos_corrupt]')) {
            res.shouldInject = true;
            res.faultType = FaultType.MUTATED_DATA;
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
'''

APEX_ENGINE_META = '''<?xml version="1.0" encoding="UTF-8"?>
<ApexClass xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>61.0</apiVersion>
    <status>Active</status>
</ApexClass>
'''

CASE_ACTION_CLS = '''/**
 * CaseSupportChaosAction.cls
 * Production-ready Case Management Invocable Action for Agentforce.
 * Demonstrates how to use AgentChaosEngine to add fault injection to Case operations.
 */
public with sharing class CaseSupportChaosAction {

    public class Request {
        @InvocableVariable(required=true description='Subject of the customer case')
        public String subject;

        @InvocableVariable(required=true description='Customer email address')
        public String customerEmail;

        @InvocableVariable(description='Case Priority: Low, Medium, High')
        public String priority;

        @InvocableVariable(description='Optional chaos directive: [CHAOS_DML], [CHAOS_CPU_TIMEOUT], [CHAOS_DELAY_14S]')
        public String chaosDirective;
    }

    public class Result {
        @InvocableVariable(description='Whether the case creation succeeded')
        public Boolean isSuccess;

        @InvocableVariable(description='Created Case ID if successful')
        public String caseId;

        @InvocableVariable(description='Created 8-digit Case Number if successful')
        public String caseNumber;

        @InvocableVariable(description='Error message if operation failed')
        public String errorMessage;
    }

    @InvocableMethod(
        label='Create Support Case (AgentChaos Enabled)'
        description='Creates a customer case with pluggable chaos testing hooks for Agentforce'
    )
    public static List<Result> createSupportCase(List<Request> requests) {
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
'''

CASE_ACTION_META = '''<?xml version="1.0" encoding="UTF-8"?>
<ApexClass xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>61.0</apiVersion>
    <status>Active</status>
</ApexClass>
'''


def export_apex_classes(output_dir: str | Path) -> Dict[str, str]:
    """Export all deployable Apex classes and metadata files to the target directory."""
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    files = {
        "AgentChaosEngine.cls": APEX_ENGINE_CLS,
        "AgentChaosEngine.cls-meta.xml": APEX_ENGINE_META,
        "CaseSupportChaosAction.cls": CASE_ACTION_CLS,
        "CaseSupportChaosAction.cls-meta.xml": CASE_ACTION_META,
    }

    created_paths = {}
    for filename, content in files.items():
        file_path = target / filename
        file_path.write_text(content, encoding="utf-8")
        created_paths[filename] = str(file_path.resolve())

    return created_paths
