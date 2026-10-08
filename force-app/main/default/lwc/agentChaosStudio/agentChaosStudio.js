import { LightningElement, track, wire } from 'lwc';
import getAvailableActions from '@salesforce/apex/AgentChaosStudioController.getAvailableActions';
import getActiveRules from '@salesforce/apex/AgentChaosStudioController.getActiveRules';
import auditAction from '@salesforce/apex/AgentChaosStudioController.auditAction';
import { ShowToastEvent } from 'lightning/platformShowToastEvent';

export default class AgentChaosStudio extends LightningElement {
    @track actionOptions = [];
    @track selectedAction = 'Create_Support_Case_Chaos';
    @track report = null;
    @track rules = [];
    @track isLoading = false;

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

    connectedCallback() {
        // Auto-run audit on initialization for instant visual gratification
        this.runAuditForAction(this.selectedAction);
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
