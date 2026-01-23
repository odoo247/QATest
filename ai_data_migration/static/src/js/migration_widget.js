/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Migration Progress Widget
 * Displays real-time progress for ongoing imports
 */
export class MigrationProgressWidget extends Component {
    static template = "ai_data_migration.MigrationProgress";
    static props = {
        projectId: { type: Number },
        autoRefresh: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        
        this.state = useState({
            progress: 0,
            imported: 0,
            errors: 0,
            total: 0,
            status: 'draft',
            isLoading: true,
        });

        onWillStart(async () => {
            await this.loadProgress();
            if (this.props.autoRefresh) {
                this.startAutoRefresh();
            }
        });
    }

    async loadProgress() {
        try {
            const project = await this.orm.read(
                "migration.project",
                [this.props.projectId],
                ["progress", "imported_count", "error_count", "total_rows", "state"]
            );
            
            if (project.length) {
                const data = project[0];
                this.state.progress = data.progress || 0;
                this.state.imported = data.imported_count || 0;
                this.state.errors = data.error_count || 0;
                this.state.total = data.total_rows || 0;
                this.state.status = data.state;
            }
        } catch (error) {
            console.error("Failed to load migration progress:", error);
        } finally {
            this.state.isLoading = false;
        }
    }

    startAutoRefresh() {
        this.refreshInterval = setInterval(async () => {
            await this.loadProgress();
            if (this.state.status === 'done' || this.state.status === 'error') {
                this.stopAutoRefresh();
            }
        }, 2000);
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
    }

    get progressColor() {
        if (this.state.status === 'error') return '#dc3545';
        if (this.state.status === 'done') return '#28a745';
        return '#007bff';
    }

    willUnmount() {
        this.stopAutoRefresh();
    }
}

/**
 * Column Mapping Preview Widget
 * Shows source data samples alongside target field info
 */
export class ColumnMappingPreview extends Component {
    static template = "ai_data_migration.ColumnMappingPreview";
    static props = {
        sourceColumn: { type: String },
        sampleValues: { type: Array, optional: true },
        targetField: { type: Object, optional: true },
        confidence: { type: Number, optional: true },
    };

    get confidenceClass() {
        const conf = this.props.confidence || 0;
        if (conf >= 0.8) return 'ai-confidence-high';
        if (conf >= 0.5) return 'ai-confidence-medium';
        return 'ai-confidence-low';
    }

    get confidenceIcon() {
        const conf = this.props.confidence || 0;
        if (conf >= 0.8) return '🟢';
        if (conf >= 0.5) return '🟡';
        return '🔴';
    }
}

/**
 * Data Quality Indicator Widget
 */
export class DataQualityIndicator extends Component {
    static template = "ai_data_migration.DataQualityIndicator";
    static props = {
        score: { type: Number },
        issues: { type: Array, optional: true },
    };

    get scoreClass() {
        if (this.props.score >= 0.8) return 'score-high';
        if (this.props.score >= 0.5) return 'score-medium';
        return 'score-low';
    }

    get scorePercent() {
        return Math.round(this.props.score * 100);
    }

    get scoreLabel() {
        if (this.props.score >= 0.8) return 'Excellent';
        if (this.props.score >= 0.6) return 'Good';
        if (this.props.score >= 0.4) return 'Fair';
        return 'Poor';
    }
}

/**
 * Migration Log Viewer Component
 */
export class MigrationLogViewer extends Component {
    static template = "ai_data_migration.MigrationLogViewer";
    static props = {
        projectId: { type: Number },
        limit: { type: Number, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            logs: [],
            isLoading: true,
            filter: 'all',
        });

        onWillStart(async () => {
            await this.loadLogs();
        });
    }

    async loadLogs() {
        this.state.isLoading = true;
        try {
            const domain = [['project_id', '=', this.props.projectId]];
            
            if (this.state.filter !== 'all') {
                domain.push(['log_level', '=', this.state.filter]);
            }

            this.state.logs = await this.orm.searchRead(
                "migration.log",
                domain,
                ["action_type", "log_level", "message", "row_number", "create_date"],
                { limit: this.props.limit || 100, order: "create_date desc" }
            );
        } catch (error) {
            console.error("Failed to load logs:", error);
        } finally {
            this.state.isLoading = false;
        }
    }

    setFilter(filter) {
        this.state.filter = filter;
        this.loadLogs();
    }

    getLogClass(level) {
        const classes = {
            'error': 'log-error',
            'warning': 'log-warning',
            'success': 'log-success',
            'info': 'log-info',
        };
        return classes[level] || 'log-info';
    }

    formatTimestamp(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        return date.toLocaleTimeString();
    }
}

/**
 * Helper function to format file sizes
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Helper function to detect file type from extension
 */
function detectFileType(filename) {
    if (!filename) return 'unknown';
    const ext = filename.split('.').pop().toLowerCase();
    const types = {
        'csv': 'csv',
        'xlsx': 'excel',
        'xls': 'excel',
        'json': 'json',
    };
    return types[ext] || 'unknown';
}

// Register components
registry.category("components").add("MigrationProgressWidget", MigrationProgressWidget);
registry.category("components").add("ColumnMappingPreview", ColumnMappingPreview);
registry.category("components").add("DataQualityIndicator", DataQualityIndicator);
registry.category("components").add("MigrationLogViewer", MigrationLogViewer);

// Export utilities
export const migrationUtils = {
    formatFileSize,
    detectFileType,
};
