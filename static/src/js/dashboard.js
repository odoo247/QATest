/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class QADashboard extends Component {
    static template = "qa_test_generator.Dashboard";
    
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        
        this.state = useState({
            totalSpecs: 0,
            totalTests: 0,
            pendingTests: 0,
            passRate: 0,
            recentRuns: [],
            failedTests: [],
            loading: true,
        });
        
        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }
    
    async loadDashboardData() {
        try {
            const result = await this.orm.call(
                "qa.test.spec",
                "get_dashboard_data",
                []
            );
            
            if (result) {
                this.state.totalSpecs = result.total_specs || 0;
                this.state.totalTests = result.total_tests || 0;
                this.state.pendingTests = result.pending_tests || 0;
                this.state.passRate = result.pass_rate || 0;
                this.state.recentRuns = result.recent_runs || [];
                this.state.failedTests = result.failed_tests || [];
            }
        } catch (error) {
            console.error("Failed to load dashboard data:", error);
        } finally {
            this.state.loading = false;
        }
    }
    
    onNewSpec() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "qa.test.spec",
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }
    
    onRunAll() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "qa.test.run.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
        });
    }
    
    onViewResults() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "qa.test.result",
            view_mode: "tree,form",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }
    
    onConfig() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "qa.test.ai.config",
            view_mode: "tree,form",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }
    
    onViewRun(runId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "qa.test.run",
            res_id: runId,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }
    
    onViewTest(testId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "qa.test.case",
            res_id: testId,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }
    
    getStatusBadgeClass(status) {
        const classes = {
            passed: "badge bg-success",
            failed: "badge bg-danger",
            error: "badge bg-warning",
            running: "badge bg-info",
            pending: "badge bg-secondary",
        };
        return classes[status] || "badge bg-secondary";
    }
    
    formatDate(dateStr) {
        if (!dateStr) return "-";
        const date = new Date(dateStr);
        return date.toLocaleDateString() + " " + date.toLocaleTimeString();
    }
}

QADashboard.template = "qa_test_generator.Dashboard";

registry.category("actions").add("qa_test_dashboard", QADashboard);

export default QADashboard;
