odoo.define('inspection_station_service.dashboard', function (require) {
    'use strict';

    var AbstractAction = require('web.AbstractAction');
    var core = require('web.core');
    var rpc = require('web.rpc');

    var _t = core._t;

    /**
     * Inspection Station Service — Dashboard
     *
     * Renders four Chart.js charts:
     *   1. Doughnut/Pie  – score distribution (Excellent / Bon / Moyen / Faible)
     *   2. Bar            – average score per site
     *   3. Radar          – average score per question category
     *   4. Line           – monthly score trend (12 months rolling)
     */
    var InspectionDashboard = AbstractAction.extend({

        template: 'InspectionDashboard',

        // Stores Chart.js instances so we can destroy them before re-rendering
        _charts: {},

        // ──────────────────────────────────────────────────────────────────
        // Lifecycle
        // ──────────────────────────────────────────────────────────────────

        init: function (parent, action) {
            this._super.apply(this, arguments);
            this._currentPeriod = 'all';
        },

        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                self._bindToolbar();
                self._bindActionButtons();
                return self._loadAndRender();
            });
        },

        destroy: function () {
            this._destroyCharts();
            this._super.apply(this, arguments);
        },

        // ──────────────────────────────────────────────────────────────────
        // Event binding
        // ──────────────────────────────────────────────────────────────────

        _bindToolbar: function () {
            var self = this;
            this.$('.o_period_btn').on('click', function () {
                self.$('.o_period_btn').removeClass('active');
                $(this).addClass('active');
                self._currentPeriod = $(this).data('period');
                self._loadAndRender();
            });
        },

        _bindActionButtons: function () {
            var self = this;
            this.$('.o_action_btn').on('click', function () {
                var action = $(this).data('action');
                self._doNavigate(action);
            });
        },

        _doNavigate: function (action) {
            var actionMap = {
                'new_inspection':   'inspection_station_service.action_inspection_report_new',
                'all_inspections':  'inspection_station_service.action_inspection_report',
                'sites':            'inspection_station_service.action_inspection_site',
                'templates':        'inspection_station_service.action_inspection_template',
            };
            if (actionMap[action]) {
                this.do_action(actionMap[action]);
            }
        },

        // ──────────────────────────────────────────────────────────────────
        // Data loading
        // ──────────────────────────────────────────────────────────────────

        _buildDomain: function () {
            var domain = [];
            var now = new Date();

            if (this._currentPeriod === 'year') {
                var yearStart = now.getFullYear() + '-01-01';
                domain = [['date', '>=', yearStart]];
            } else if (this._currentPeriod === 'month') {
                var y = now.getFullYear();
                var m = String(now.getMonth() + 1).padStart(2, '0');
                domain = [['date', '>=', y + '-' + m + '-01']];
            }
            return domain;
        },

        _loadAndRender: function () {
            var self = this;
            var domain = this._buildDomain();

            return rpc.query({
                model:  'inspection.report',
                method: 'get_dashboard_data',
                args:   [domain],
                kwargs: {},
            }).then(function (data) {
                self._destroyCharts();
                self._renderKPIs(data.kpis);
                self._renderPieChart(data.score_distribution);
                self._renderBarChart(data.sites_scores);
                self._renderRadarChart(data.radar);
                self._renderLineChart(data.monthly);
            }).guardedCatch(function (err) {
                console.error('[InspectionDashboard] Erreur de chargement :', err);
            });
        },

        // ──────────────────────────────────────────────────────────────────
        // KPI rendering
        // ──────────────────────────────────────────────────────────────────

        _renderKPIs: function (kpis) {
            this.$('#kpi-total').text(kpis.total || 0);
            this.$('#kpi-validated').text(kpis.validated || 0);
            this.$('#kpi-inprogress').text(kpis.in_progress || 0);
            this.$('#kpi-avgscore').text((kpis.avg_score || 0).toFixed(1) + '%');
            this.$('#kpi-sites').text(kpis.sites_count || 0);
            this.$('#kpi-templates').text(kpis.templates_count || 0);
        },

        // ──────────────────────────────────────────────────────────────────
        // Chart helpers
        // ──────────────────────────────────────────────────────────────────

        _destroyCharts: function () {
            _.each(this._charts, function (chart) {
                if (chart) { chart.destroy(); }
            });
            this._charts = {};
        },

        _getCanvas: function (id) {
            var $canvas = this.$('#' + id);
            return $canvas.length ? $canvas[0] : null;
        },

        // ──────────────────────────────────────────────────────────────────
        // 1. Doughnut / Pie chart — score distribution
        // ──────────────────────────────────────────────────────────────────

        _renderPieChart: function (data) {
            var total = (data.data || []).reduce(function (a, b) { return a + b; }, 0);
            if (!total) {
                this.$('#pie-empty').show();
                this.$('#pieChart').hide();
                return;
            }
            this.$('#pie-empty').hide();
            this.$('#pieChart').show();

            var canvas = this._getCanvas('pieChart');
            if (!canvas) { return; }

            this._charts.pie = new Chart(canvas.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels:   data.labels,
                    datasets: [{
                        data:            data.data,
                        backgroundColor: data.colors || ['#28a745', '#17a2b8', '#ffc107', '#dc3545'],
                        borderWidth:     3,
                        borderColor:     '#fff',
                    }],
                },
                options: {
                    responsive:          true,
                    maintainAspectRatio: true,
                    cutoutPercentage:    55,
                    legend: {
                        position: 'bottom',
                        labels: { padding: 16, usePointStyle: true },
                    },
                    tooltips: {
                        callbacks: {
                            label: function (item, d) {
                                var label = d.labels[item.index] || '';
                                var value = d.datasets[0].data[item.index];
                                return ' ' + label + ' : ' + value + ' inspection(s)';
                            },
                        },
                    },
                },
            });
        },

        // ──────────────────────────────────────────────────────────────────
        // 2. Bar chart — average score per site
        // ──────────────────────────────────────────────────────────────────

        _renderBarChart: function (data) {
            if (!data.labels || !data.labels.length) {
                this.$('#bar-empty').show();
                this.$('#barChart').hide();
                return;
            }
            this.$('#bar-empty').hide();
            this.$('#barChart').show();

            var canvas = this._getCanvas('barChart');
            if (!canvas) { return; }

            // Colour gradient based on score value
            var colors = data.data.map(function (v) {
                if (v >= 80) { return 'rgba(40, 167, 69, 0.75)'; }
                if (v >= 60) { return 'rgba(23, 162, 184, 0.75)'; }
                if (v >= 40) { return 'rgba(255, 193, 7, 0.75)'; }
                return 'rgba(220, 53, 69, 0.75)';
            });

            this._charts.bar = new Chart(canvas.getContext('2d'), {
                type: 'bar',
                data: {
                    labels:   data.labels,
                    datasets: [{
                        label:           'Score moyen (%)',
                        data:            data.data,
                        backgroundColor: colors,
                        borderColor:     colors.map(function (c) {
                            return c.replace('0.75', '1');
                        }),
                        borderWidth: 1,
                    }],
                },
                options: {
                    responsive:          true,
                    maintainAspectRatio: false,
                    legend: { display: false },
                    scales: {
                        yAxes: [{
                            ticks: {
                                min:      0,
                                max:      100,
                                stepSize: 20,
                                callback: function (v) { return v + '%'; },
                            },
                            gridLines: { color: 'rgba(0,0,0,0.05)' },
                        }],
                        xAxes: [{
                            gridLines: { display: false },
                            ticks: {
                                maxRotation: 40,
                                minRotation: 0,
                            },
                        }],
                    },
                    tooltips: {
                        callbacks: {
                            label: function (item) {
                                return ' ' + item.yLabel.toFixed(1) + '%';
                            },
                        },
                    },
                },
            });
        },

        // ──────────────────────────────────────────────────────────────────
        // 3. Radar chart — score by category
        // ──────────────────────────────────────────────────────────────────

        _renderRadarChart: function (data) {
            if (!data.labels || data.labels.length < 2) {
                this.$('#radar-empty').show();
                this.$('#radarChart').hide();
                return;
            }
            this.$('#radar-empty').hide();
            this.$('#radarChart').show();

            var canvas = this._getCanvas('radarChart');
            if (!canvas) { return; }

            this._charts.radar = new Chart(canvas.getContext('2d'), {
                type: 'radar',
                data: {
                    labels:   data.labels,
                    datasets: [{
                        label:           'Score moyen par catégorie (%)',
                        data:            data.data,
                        backgroundColor: 'rgba(79, 70, 229, 0.15)',
                        borderColor:     'rgba(79, 70, 229, 0.9)',
                        borderWidth:     2,
                        pointBackgroundColor: 'rgba(79, 70, 229, 1)',
                        pointBorderColor:     '#fff',
                        pointRadius:          5,
                        pointHoverRadius:     7,
                    }],
                },
                options: {
                    responsive:          true,
                    maintainAspectRatio: true,
                    scale: {
                        ticks: {
                            min:      0,
                            max:      100,
                            stepSize: 20,
                            display:  true,
                            callback: function (v) { return v + '%'; },
                        },
                        gridLines:   { color: 'rgba(0,0,0,0.08)' },
                        angleLines:  { color: 'rgba(0,0,0,0.1)' },
                        pointLabels: { fontSize: 12 },
                    },
                    legend: {
                        position: 'bottom',
                        labels:   { usePointStyle: true, padding: 12 },
                    },
                    tooltips: {
                        callbacks: {
                            label: function (item, d) {
                                var val = d.datasets[item.datasetIndex].data[item.index];
                                return ' ' + (val || 0).toFixed(1) + '%';
                            },
                        },
                    },
                },
            });
        },

        // ──────────────────────────────────────────────────────────────────
        // 4. Line chart — monthly trend
        // ──────────────────────────────────────────────────────────────────

        _renderLineChart: function (data) {
            var canvas = this._getCanvas('lineChart');
            if (!canvas) { return; }

            this._charts.line = new Chart(canvas.getContext('2d'), {
                type: 'line',
                data: {
                    labels:   data.labels || [],
                    datasets: [{
                        label:           'Score mensuel moyen (%)',
                        data:            data.data || [],
                        borderColor:     'rgba(23, 162, 184, 1)',
                        backgroundColor: 'rgba(23, 162, 184, 0.1)',
                        borderWidth:     2,
                        pointRadius:     4,
                        pointBackgroundColor: 'rgba(23, 162, 184, 1)',
                        pointBorderColor:     '#fff',
                        fill:            true,
                        tension:         0.35,
                    }],
                },
                options: {
                    responsive:          true,
                    maintainAspectRatio: false,
                    legend: {
                        position: 'bottom',
                        labels:   { usePointStyle: true },
                    },
                    scales: {
                        yAxes: [{
                            ticks: {
                                min:      0,
                                max:      100,
                                stepSize: 20,
                                callback: function (v) { return v + '%'; },
                            },
                            gridLines: { color: 'rgba(0,0,0,0.05)' },
                        }],
                        xAxes: [{
                            gridLines: { color: 'rgba(0,0,0,0.04)' },
                            ticks:     { maxRotation: 30, minRotation: 0 },
                        }],
                    },
                    tooltips: {
                        mode:      'index',
                        intersect: false,
                        callbacks: {
                            label: function (item) {
                                return ' ' + (item.yLabel || 0).toFixed(1) + '%';
                            },
                        },
                    },
                },
            });
        },
    });

    // Register the client action
    core.action_registry.add(
        'inspection_station_service.dashboard',
        InspectionDashboard
    );

    return InspectionDashboard;
});
