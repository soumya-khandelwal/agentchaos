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

    // Service Agent Simulator State
    @track agentOptions = [];
    @track selectedAgent = 'Customer_Support_Agent';
    @track chatPrompt = 'I need to open a support case for a broken delivery. Email: chaos-dml@test.com, Subject: Crushed Box.';
    @track agentTurnResult = null;

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
            this.showToast('Error', 'Failed to retrieve available actions: ' + error.body.message, 'error');
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
        // Auto-run action audit on initialization
        this.runAuditForAction(this.selectedAction);
        // Auto-run initial agent turn
        this.runTurnSimulation();
    }

    handleActionChange(event) {
        this.selectedAction = event.detail.value;
    }

    handleRunAudit() {
        this.runAuditForAction(this.selectedAction);
    }

    runAuditForAction(actionName) {
        this.isLoading = true;
        auditAction({ actionName: actionName })
            .then(result => {
                this.report = result;
                this.isLoading = false;
                const statusTitle = result.passed ? 'Audit Passed' : 'Issues Detected';
                const toastVariant = result.passed ? 'success' : 'warning';
                this.showToast(
                    statusTitle,
                    `Action [${result.actionName}] audited: ${result.passedVectors}/${result.totalVectors} vectors clean (${result.overallScore}% score).`,
                    toastVariant
                );
            })
            .catch(error => {
                this.isLoading = false;
                const errMsg = error.body ? error.body.message : error.message;
                this.showToast('Audit Failed', errMsg, 'error');
            });
    }

    // Service Agent simulator handlers
    handleAgentChange(event) {
        this.selectedAgent = event.detail.value;
    }

    handleChatPromptChange(event) {
        this.chatPrompt = event.detail.value;
    }

    handlePresetDml() {
        this.chatPrompt = 'I need to report another broken item. Email: chaos-dml@test.com, Subject: Crushed Box.';
        this.runTurnSimulation();
    }

    handlePresetTimeout() {
        this.chatPrompt = 'The package was delayed and never showed up. Escalate a case immediately. [CHAOS_DELAY_14S]';
        this.runTurnSimulation();
    }

    handlePresetLoop() {
        this.chatPrompt = 'I need to open a support case for a delivery problem. Email: retry-fail@test.com, Subject: Damaged Box.';
        this.runTurnSimulation();
    }

    handlePresetNormal() {
        this.chatPrompt = 'I need to open a support case for a broken delivery. Email: customer@example.com, Subject: Damaged Parcel.';
        this.runTurnSimulation();
    }

    handleSendTurn() {
        this.runTurnSimulation();
    }

    runTurnSimulation() {
        this.isLoading = true;
        simulateAgentTurn({ agentName: this.selectedAgent, userQuery: this.chatPrompt })
            .then(result => {
                this.agentTurnResult = result;
                this.isLoading = false;
            })
            .catch(error => {
                this.isLoading = false;
                const errMsg = error.body ? error.body.message : error.message;
                this.showToast('Simulation Failed', errMsg, 'error');
            });
    }

    get scoreColorClass() {
        if (!this.report) return '';
        if (this.report.overallScore >= 80) return 'slds-text-color_success font-bold';
        if (this.report.overallScore >= 50) return 'slds-text-color_warning font-bold';
        return 'slds-text-color_error font-bold';
    }

    get verdictBadgeClass() {
        if (!this.report) return '';
        return this.report.passed ? 'slds-badge slds-theme_success' : 'slds-badge slds-theme_error';
    }

    get verdictText() {
        if (!this.report) return '';
        return this.report.passed ? 'READY FOR PRODUCTION' : 'ACTION REQUIRED / AT RISK';
    }

    showToast(title, message, variant) {
        const evt = new ShowToastEvent({
            title: title,
            message: message,
            variant: variant,
        });
        this.dispatchEvent(evt);
    }
}
