import { LightningElement, track, wire } from 'lwc';
import getAvailableActions from '@salesforce/apex/AgentChaosStudioController.getAvailableActions';
import getActiveRules from '@salesforce/apex/AgentChaosStudioController.getActiveRules';
import auditAction from '@salesforce/apex/AgentChaosStudioController.auditAction';
import getAvailableAgents from '@salesforce/apex/AgentChaosStudioController.getAvailableAgents';
import simulateAgentTurn from '@salesforce/apex/AgentChaosStudioController.simulateAgentTurn';
import { ShowToastEvent } from 'lightning/platformShowToastEvent';

export default class AgentChaosStudio extends LightningElement {
    @track actionOptions = [];
    @track selectedAction = 'Create_Support_Case_Chaos';
    @track report = null;
    @track rules = [];
    @track isLoading = false;
    @track testProgressPercent = 0;
    @track currentTestStepText = '';

    // Live In-Page Notifications & Audit Terminal Logs
    @track bannerMessage = '';
    @track bannerClass = '';
    @track bannerType = '';
    @track auditLogs = [];
    @track showTechnicalLogs = false;

    // Service Agent Multi-Turn Simulator State
    @track agentOptions = [];
    @track selectedAgent = 'Customer_Support_Agent';
    @track chatPrompt = 'I need to open a support case for a broken delivery. Email: chaos-dml@test.com, Subject: Crushed Box.';
    @track conversationHistory = [];

    logCounter = 1;

    @wire(getAvailableActions)
    wiredActions({ error, data }) {
        if (data) {
            this.actionOptions = data.map(item => ({
                label: item.label,
                value: item.value,
                description: item.description
            }));
            if (this.actionOptions.length > 0 && !this.selectedAction) {
                this.selectedAction = this.actionOptions[0].value;
            }
        } else if (error) {
            this.showBanner('Failed to load actions from org: ' + (error.body ? error.body.message : error.message), 'error');
        }
    }

    @wire(getActiveRules)
    wiredRules({ error, data }) {
        if (data) {
            this.rules = data;
        } else if (error) {
            console.error('Error fetching active rules', error);
        }
    }

    @wire(getAvailableAgents)
    wiredAgents({ error, data }) {
        if (data) {
            this.agentOptions = data.map(item => ({
                label: item.label,
                value: item.value,
                description: item.description
            }));
            if (this.agentOptions.length > 0 && !this.selectedAgent) {
                this.selectedAgent = this.agentOptions[0].value;
            }
        } else if (error) {
            console.error('Error fetching agents', error);
        }
    }

    connectedCallback() {
        this.addLog(`⚡ AgentChaos Studio initialized in org.`);
        this.addLog(`Connected to org limits: 100 SOQL queries / 10,000ms Apex CPU timeout.`);
        
        // Populate initial conversation turn
        this.conversationHistory = [
            {
                id: 'init-1',
                userQuery: 'I need to open a support case for a broken delivery. Email: customer@example.com, Subject: Damaged Parcel.',
                agentResponse: 'Your support case has been successfully created! Case Number: 00001027. A customer support representative will follow up with you shortly.',
                actionCalled: 'Create_Support_Case_Chaos',
                faultInjected: 'NONE (Normal Flow)',
                durationSeconds: 1.25,
                slaCompliant: true,
                isEscalatedToHuman: false,
                isHallucinationClean: true
            }
        ];

        // Run initial action audit
        this.executeAudit();
    }

    handleActionChange(event) {
        this.selectedAction = event.detail.value;
        this.addLog(`Target action changed to: ${this.selectedAction}`);
    }

    handleRunAudit() {
        this.executeAudit();
    }

    executeAudit() {
        this.isLoading = true;
        this.testProgressPercent = 15;
        this.currentTestStepText = 'Initializing safety audit in Apex runtime...';
        this.addLog(`🚀 Running 6 safety tests on: [${this.selectedAction}]`);

        // Step by step visual progress simulation so user sees what is being audited
        setTimeout(() => {
            this.testProgressPercent = 40;
            this.currentTestStepText = 'Testing missing fields & null safety (Vectors 1 & 2)...';
            this.addLog(`⚡ [Test 1 & 2] Injected missing fields and null arguments. Verifying no crashes.`);
        }, 200);

        setTimeout(() => {
            this.testProgressPercent = 75;
            this.currentTestStepText = 'Testing runaway loops, governor limits & timeouts (Vectors 3, 4, 5)...';
            this.addLog(`⚡ [Test 3 & 4] Simulating runaway ReAct loop. Verifying safety stop triggers.`);
        }, 450);

        setTimeout(() => {
            this.testProgressPercent = 90;
            this.currentTestStepText = 'Testing Data Cloud knowledge retrieval (Vector 6)...';
            this.addLog(`⚡ [Test 6] Simulating empty search result from Data Cloud. Verifying agent doesn\'t fabricate.`);
            
            // Call Apex controller
            auditAction({ actionName: this.selectedAction })
                .then(result => {
                    this.report = result;
                    this.testProgressPercent = 100;
                    this.isLoading = false;

                    this.addLog(`✅ Audit Complete! ${result.passedVectors} of ${result.totalVectors} tests passed. Overall Score: ${result.overallScore}%.`);
                    this.showBanner(`✓ Audit Complete for [${result.actionName}] — ${result.passedVectors} of ${result.totalVectors} tests passed cleanly! (0 Flex Credits Used)`, 'success');
                })
                .catch(error => {
                    this.isLoading = false;
                    const errMsg = error.body ? error.body.message : error.message;
                    this.addLog(`❌ Audit Error: ${errMsg}`);
                    this.showBanner('Audit Failed: ' + errMsg, 'error');
                });
        }, 700);
    }

    // Service Agent Simulator Handlers
    handleAgentChange(event) {
        this.selectedAgent = event.detail.value;
        this.addLog(`Active Service Agent switched to: ${this.selectedAgent}`);
    }

    handleChatPromptChange(event) {
        this.chatPrompt = event.detail.value;
    }

    handlePresetDml() {
        this.chatPrompt = 'I need to report another broken item. Email: chaos-dml@test.com, Subject: Crushed Box.';
        this.addLog(`👉 Clicked preset: Missing Required Field (Validation Rollback)`);
        this.sendTurn();
    }

    handlePresetTimeout() {
        this.chatPrompt = 'The package was delayed and never showed up. Escalate a case immediately. [CHAOS_DELAY_14S]';
        this.addLog(`👉 Clicked preset: 14-Second Timeout Cliff`);
        this.sendTurn();
    }

    handlePresetLoop() {
        this.chatPrompt = 'I need to open a support case for a delivery problem. Email: retry-fail@test.com, Subject: Damaged Box.';
        this.addLog(`👉 Clicked preset: Runaway Infinite Loop`);
        this.sendTurn();
    }

    handlePresetNormal() {
        this.chatPrompt = 'I need to open a support case for a broken delivery. Email: customer@example.com, Subject: Damaged Parcel.';
        this.addLog(`👉 Clicked preset: Normal Operational Flow`);
        this.sendTurn();
    }

    handleSendTurn() {
        this.sendTurn();
    }

    sendTurn() {
        const queryText = this.chatPrompt;
        if (!queryText || queryText.trim() === '') return;

        this.isLoading = true;
        this.addLog(`💬 Customer sent: "${queryText.substring(0, 60)}..."`);

        simulateAgentTurn({ agentName: this.selectedAgent, userQuery: queryText })
            .then(result => {
                this.isLoading = false;
                const turnId = 'turn-' + Date.now();
                const newTurn = {
                    id: turnId,
                    userQuery: result.userQuery,
                    agentResponse: result.agentResponse,
                    actionCalled: result.actionCalled,
                    faultInjected: result.faultInjected,
                    durationSeconds: result.durationSeconds,
                    slaCompliant: result.slaCompliant,
                    isEscalatedToHuman: result.isEscalatedToHuman,
                    isHallucinationClean: result.isHallucinationClean
                };

                // Prepend new turn to conversation history
                this.conversationHistory = [newTurn, ...this.conversationHistory];

                this.addLog(`🤖 Agent replied: "${result.agentResponse.substring(0, 70)}..."`);
                if (result.isEscalatedToHuman) {
                    this.addLog(`🛡️ Safety Triggered: Agent escalated customer to live human queue.`);
                    this.showBanner(`Live Safety Triggered: Action failed safely and agent transferred customer to a human representative!`, 'success');
                } else {
                    this.showBanner(`Agent Turn Processed: Request resolved cleanly.`, 'info');
                }
            })
            .catch(error => {
                this.isLoading = false;
                const errMsg = error.body ? error.body.message : error.message;
                this.addLog(`❌ Agent Simulation Error: ${errMsg}`);
                this.showBanner('Agent Error: ' + errMsg, 'error');
            });
    }

    handleClearLogs() {
        this.auditLogs = [];
        this.addLog('Log cleared.');
    }

    handleToggleLogs() {
        this.showTechnicalLogs = !this.showTechnicalLogs;
    }

    get logToggleLabel() {
        return this.showTechnicalLogs ? '▼ Hide Technical Activity Logs' : '▶ Show Technical Activity Logs';
    }

    get logToggleIcon() {
        return this.showTechnicalLogs ? 'utility:chevrondown' : 'utility:chevronright';
    }

    addLog(text) {
        const timestamp = new Date().toLocaleTimeString();
        this.auditLogs = [
            { id: this.logCounter++, text: `[${timestamp}] ${text}` },
            ...this.auditLogs.slice(0, 25) // Keep last 25 lines
        ];
    }

    showBanner(msg, type) {
        this.bannerMessage = msg;
        this.bannerType = type;
        if (type === 'success') {
            this.bannerClass = 'slds-notify slds-notify_alert slds-theme_success slds-m-bottom_medium banner-anim';
        } else if (type === 'error') {
            this.bannerClass = 'slds-notify slds-notify_alert slds-theme_error slds-m-bottom_medium banner-anim';
        } else {
            this.bannerClass = 'slds-notify slds-notify_alert slds-theme_info slds-m-bottom_medium banner-anim';
        }

        // Auto-dismiss after 6 seconds
        setTimeout(() => {
            if (this.bannerMessage === msg) {
                this.bannerMessage = '';
            }
        }, 6000);
    }

    get scoreColorClass() {
        if (!this.report) return '';
        if (this.report.overallScore >= 80) return 'slds-text-color_success font-bold';
        if (this.report.overallScore >= 50) return 'slds-text-color_warning font-bold';
        return 'slds-text-color_error font-bold';
    }

    get verdictBadgeClass() {
        if (!this.report) return '';
        return this.report.passed ? 'slds-badge slds-theme_success font-bold' : 'slds-badge slds-theme_error font-bold';
    }

    get verdictText() {
        if (!this.report) return '';
        return this.report.passed ? 'READY FOR PRODUCTION' : 'ACTION REQUIRED / AT RISK';
    }
}
