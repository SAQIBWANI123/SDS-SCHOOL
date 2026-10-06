/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

const GENDER_COLORS = { male: "#0ea5e9", female: "#f472b6", other: "#f59e0b" };
const GENDER_LABELS = { male: "Boys", female: "Girls", other: "Other" };

export class CampusPulseDashboard extends Component {
    static template = "smartdesk_school_management.CampusPulseDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loading: true, data: null, error: false });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call("school.dashboard", "get_dashboard_data", []);
            this.state.error = false;
        } catch (e) {
            this.state.error = true;
        }
        this.state.loading = false;
    }

    // ---------------------------------------------------------- helpers
    get greeting() {
        const h = new Date().getHours();
        return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
    }

    get todayLabel() {
        return new Date().toLocaleDateString(undefined, {
            weekday: "long", day: "numeric", month: "long", year: "numeric",
        });
    }

    money(value) {
        const cur = this.state.data.currency;
        const n = Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
        return cur.position === "after" ? `${n} ${cur.symbol}` : `${cur.symbol}${n}`;
    }

    compact(value) {
        const v = Number(value || 0);
        const cur = this.state.data.currency.symbol;
        if (v >= 1e6) return `${cur}${(v / 1e6).toFixed(1)}M`;
        if (v >= 1e3) return `${cur}${(v / 1e3).toFixed(1)}k`;
        return `${cur}${Math.round(v)}`;
    }

    monthShort(dateStr) {
        return new Date(dateStr + "T00:00:00").toLocaleDateString(undefined, { month: "short" });
    }

    pct(value, max) {
        return max ? Math.max(Math.round((value * 100) / max), 0) : 0;
    }

    get maxGrade() {
        return Math.max(1, ...this.state.data.grades.map((g) => g.count));
    }

    get maxFee() {
        return Math.max(1, ...this.state.data.fee_months.map((m) => Math.max(m.billed, m.collected)));
    }

    get genderSegments() {
        const g = this.state.data.gender;
        const total = (g.male || 0) + (g.female || 0) + (g.other || 0);
        let offset = 0;
        const out = [];
        for (const key of ["male", "female", "other"]) {
            const value = g[key] || 0;
            const len = total ? (value * 100) / total : 0;
            out.push({
                key, value, len, offset,
                color: GENDER_COLORS[key], label: GENDER_LABELS[key],
                pct: total ? Math.round(len) : 0,
            });
            offset += len;
        }
        return out;
    }

    get genderTotal() {
        const g = this.state.data.gender;
        return (g.male || 0) + (g.female || 0) + (g.other || 0);
    }

    get hasAttendanceData() {
        return this.state.data.attendance_week.some((d) => d.total > 0);
    }

    get hasFeeData() {
        return this.state.data.fee_months.some((m) => m.billed > 0 || m.collected > 0);
    }

    // ---------------------------------------------------------- navigation
    openList(name, model, domain = [], context = {}) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: model,
            views: [[false, "list"], [false, "form"]],
            domain,
            context,
            target: "current",
        });
    }

    openNew(name, model) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: model,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openRecord(model, id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openXml(xmlid) {
        this.action.doAction(xmlid);
    }
}

registry.category("actions").add("school_management_dashboard", CampusPulseDashboard);
