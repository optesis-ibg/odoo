# -*- coding: utf-8 -*-
import re
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class InspectionReport(models.Model):
    _name = 'inspection.report'
    _description = "Rapport d'inspection de station service"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    # ─── Identification ───────────────────────────────────────────────────────
    name = fields.Char(
        string='Référence', readonly=True, copy=False,
        default=lambda self: _('Nouveau'),
    )
    site_id = fields.Many2one(
        'inspection.site', string='Site / Station', required=True,
        tracking=True, ondelete='restrict',
    )
    template_id = fields.Many2one(
        'inspection.template', string="Modèle d'inspection", required=True,
        tracking=True,
    )
    inspector_id = fields.Many2one(
        'res.users', string='Inspecteur',
        default=lambda self: self.env.user, tracking=True,
    )
    date = fields.Date(
        string="Date d'inspection", default=fields.Date.today,
        required=True, tracking=True,
    )
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('in_progress', 'En cours'),
        ('done', 'Terminé'),
        ('validated', 'Validé'),
    ], string='Statut', default='draft', tracking=True, copy=False)

    # ─── Réponses ─────────────────────────────────────────────────────────────
    answer_ids = fields.One2many(
        'inspection.answer', 'report_id',
        string='Réponses', copy=True,
    )

    # ─── Scoring ──────────────────────────────────────────────────────────────
    total_score = fields.Float(
        string='Score obtenu',
        compute='_compute_scores', store=True,
    )
    total_max_score = fields.Float(
        string='Score maximum',
        compute='_compute_scores', store=True,
    )
    score_percent = fields.Float(
        string='Score (%)',
        compute='_compute_scores', store=True,
    )
    score_level = fields.Selection([
        ('excellent', 'Excellent'),
        ('bon', 'Bon'),
        ('moyen', 'Moyen'),
        ('faible', 'Faible'),
    ], string='Niveau',
        compute='_compute_score_level', store=True,
    )

    # ─── Observations ─────────────────────────────────────────────────────────
    note = fields.Text(string='Observations générales')
    global_signature = fields.Binary(
        string='Signature du valideur', attachment=True,
    )

    # ─── Computed ─────────────────────────────────────────────────────────────
    answered_count = fields.Integer(
        string='Questions répondues',
        compute='_compute_scores', store=True,
    )
    total_questions = fields.Integer(
        string='Total questions',
        compute='_compute_scores', store=True,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # ORM overrides
    # ──────────────────────────────────────────────────────────────────────────

    @api.model
    def create(self, vals):
        if vals.get('name', _('Nouveau')) == _('Nouveau'):
            vals['name'] = (
                self.env['ir.sequence'].next_by_code('inspection.report')
                or _('Nouveau')
            )
        return super().create(vals)

    # ──────────────────────────────────────────────────────────────────────────
    # Computed fields
    # ──────────────────────────────────────────────────────────────────────────

    @api.depends('answer_ids.score', 'answer_ids.max_score', 'answer_ids.is_answered')
    def _compute_scores(self):
        for report in self:
            answers = report.answer_ids.filtered(
                lambda a: a.question_type != 'formula'
            )
            formula_answers = report.answer_ids.filtered(
                lambda a: a.question_type == 'formula'
            )
            total = sum(a.score for a in report.answer_ids)
            max_total = sum(a.max_score for a in answers)

            answered = sum(
                1 for a in report.answer_ids if a.is_answered
            )
            report.total_score = total
            report.total_max_score = max_total
            report.score_percent = (
                (total / max_total * 100) if max_total > 0 else 0.0
            )
            report.answered_count = answered
            report.total_questions = len(report.answer_ids)

    @api.depends('score_percent')
    def _compute_score_level(self):
        for report in self:
            pct = report.score_percent
            if pct >= 80:
                report.score_level = 'excellent'
            elif pct >= 60:
                report.score_level = 'bon'
            elif pct >= 40:
                report.score_level = 'moyen'
            else:
                report.score_level = 'faible'

    # ──────────────────────────────────────────────────────────────────────────
    # Onchanges
    # ──────────────────────────────────────────────────────────────────────────

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Auto-creates answer lines from template questions."""
        if self.template_id:
            self.answer_ids = [(5, 0, 0)]
            lines = []
            for question in self.template_id.question_ids.sorted('sequence'):
                lines.append((0, 0, {
                    'question_id': question.id,
                    'score': 0.0,
                }))
            self.answer_ids = lines

    # ──────────────────────────────────────────────────────────────────────────
    # Actions / Workflow
    # ──────────────────────────────────────────────────────────────────────────

    def action_start(self):
        for rec in self:
            if rec.state == 'draft':
                rec.state = 'in_progress'

    def action_done(self):
        for rec in self:
            if rec.state == 'in_progress':
                rec._evaluate_formulas()
                rec.state = 'done'

    def action_validate(self):
        for rec in self:
            if rec.state == 'done':
                missing = rec.answer_ids.filtered(
                    lambda a: a.question_id.required and not a.is_answered
                )
                if missing:
                    names = ', '.join(a.question_id.name for a in missing)
                    raise ValidationError(
                        _("Questions obligatoires sans réponse :\n%s") % names
                    )
                rec.state = 'validated'

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'

    def action_load_questions(self):
        """Load (or reload) questions from the selected template."""
        self.ensure_one()
        if not self.template_id:
            raise UserError(_("Veuillez d'abord sélectionner un modèle d'inspection."))
        self._onchange_template_id()
        return True

    # ──────────────────────────────────────────────────────────────────────────
    # Formula evaluation
    # ──────────────────────────────────────────────────────────────────────────

    def _evaluate_formulas(self):
        """Evaluates formula-type answers using other answers' scores."""
        for report in self:
            # Build score context  {sequence: score}
            ctx = {}
            for answer in report.answer_ids:
                if answer.question_type != 'formula':
                    seq = answer.question_id.sequence
                    ctx['Q%d' % seq] = answer.score

            for answer in report.answer_ids:
                if answer.question_type == 'formula':
                    formula_raw = answer.question_id.formula or ''
                    if not formula_raw.strip():
                        continue
                    # Replace Q<n> tokens
                    formula = formula_raw
                    for key, val in ctx.items():
                        formula = re.sub(
                            r'\b' + re.escape(key) + r'\b',
                            str(float(val)),
                            formula,
                        )
                    # Safe eval: only numbers and basic operators
                    if re.match(r'^[\d\s\+\-\*\/\(\)\.]+$', formula):
                        try:
                            result = float(eval(formula))  # noqa: S307
                            answer.score = round(result, 4)
                        except Exception:
                            answer.score = 0.0
                    else:
                        answer.score = 0.0

    # ──────────────────────────────────────────────────────────────────────────
    # Dashboard data
    # ──────────────────────────────────────────────────────────────────────────

    @api.model
    def get_dashboard_data(self, domain=None):
        """Returns aggregated data for the dashboard charts."""
        domain = domain or []

        all_reports = self.search(domain)
        done_reports = all_reports.filtered(
            lambda r: r.state in ('done', 'validated')
        )

        # ── KPIs ──────────────────────────────────────────────────────────────
        avg_score = (
            sum(r.score_percent for r in done_reports) / len(done_reports)
            if done_reports else 0.0
        )
        kpis = {
            'total': len(all_reports),
            'validated': len(all_reports.filtered(lambda r: r.state == 'validated')),
            'in_progress': len(all_reports.filtered(lambda r: r.state == 'in_progress')),
            'avg_score': round(avg_score, 1),
            'sites_count': self.env['inspection.site'].search_count([]),
            'templates_count': self.env['inspection.template'].search_count([]),
        }

        # ── Score distribution (pie chart) ────────────────────────────────────
        score_dist = {
            'labels': ['Excellent (≥80%)', 'Bon (60–79%)', 'Moyen (40–59%)', 'Faible (<40%)'],
            'data': [
                len(done_reports.filtered(lambda r: r.score_percent >= 80)),
                len(done_reports.filtered(lambda r: 60 <= r.score_percent < 80)),
                len(done_reports.filtered(lambda r: 40 <= r.score_percent < 60)),
                len(done_reports.filtered(lambda r: r.score_percent < 40)),
            ],
            'colors': ['#28a745', '#17a2b8', '#ffc107', '#dc3545'],
        }

        # ── Sites comparison (bar chart) ──────────────────────────────────────
        sites_map = {}
        for report in done_reports:
            if report.site_id:
                sid = report.site_id.name
                sites_map.setdefault(sid, []).append(report.score_percent)

        site_labels = list(sites_map.keys())
        site_data = [
            round(sum(v) / len(v), 1) for v in sites_map.values()
        ]
        sites_scores = {'labels': site_labels, 'data': site_data}

        # ── Category radar (radar chart) ──────────────────────────────────────
        cat_scores = {}
        cat_max = {}
        for report in done_reports:
            for ans in report.answer_ids:
                cat = (ans.question_id.category or 'Général').strip()
                cat_scores.setdefault(cat, 0.0)
                cat_max.setdefault(cat, 0.0)
                cat_scores[cat] += ans.score
                if ans.question_type != 'formula':
                    cat_max[cat] += ans.max_score

        radar_labels = []
        radar_data = []
        for cat in cat_scores:
            max_v = cat_max.get(cat, 0)
            if max_v > 0:
                radar_labels.append(cat)
                radar_data.append(round(cat_scores[cat] / max_v * 100, 1))

        radar = {'labels': radar_labels, 'data': radar_data}

        # ── Monthly trend (line chart) ─────────────────────────────────────────
        today = date.today()
        monthly_labels = []
        monthly_data = []
        for i in range(11, -1, -1):
            m_start = (today - relativedelta(months=i)).replace(day=1)
            m_end = (m_start + relativedelta(months=1))
            month_reports = done_reports.filtered(
                lambda r, ms=m_start, me=m_end: ms <= r.date < me
            )
            monthly_labels.append(m_start.strftime('%b %Y'))
            monthly_data.append(
                round(
                    sum(r.score_percent for r in month_reports) / len(month_reports),
                    1,
                ) if month_reports else 0
            )

        monthly = {'labels': monthly_labels, 'data': monthly_data}

        return {
            'kpis': kpis,
            'score_distribution': score_dist,
            'sites_scores': sites_scores,
            'radar': radar,
            'monthly': monthly,
        }


class InspectionAnswer(models.Model):
    _name = 'inspection.answer'
    _description = "Réponse à une question d'inspection"
    _order = 'report_id, question_id'

    report_id = fields.Many2one(
        'inspection.report', string='Rapport',
        ondelete='cascade', required=True, index=True,
    )
    question_id = fields.Many2one(
        'inspection.question', string='Question',
        required=True, ondelete='restrict',
    )

    # Related for easy access in views / attrs
    question_type = fields.Selection(
        related='question_id.question_type',
        string='Type', store=True, readonly=True,
    )
    question_category = fields.Char(
        related='question_id.category',
        string='Catégorie', store=True, readonly=True,
    )
    max_score = fields.Float(
        related='question_id.max_score',
        string='Score max', store=True, readonly=True,
    )
    required = fields.Boolean(
        related='question_id.required',
        string='Obligatoire', store=True, readonly=True,
    )

    # ─── Answer fields (one per type) ─────────────────────────────────────────
    answer_text = fields.Text(string='Texte')
    answer_date = fields.Date(string='Date')
    answer_number = fields.Float(string='Nombre')
    answer_selection_id = fields.Many2one(
        'inspection.question.option', string='Sélection',
        domain="[('question_id', '=', question_id)]",
        ondelete='set null',
    )
    answer_signature = fields.Binary(string='Signature', attachment=True)
    answer_signature_name = fields.Char(
        string='Nom fichier signature', default='signature.png',
    )
    answer_barcode = fields.Char(string='Code barre')
    answer_qrcode = fields.Char(string='QR Code')
    answer_author_id = fields.Many2one('res.users', string='Auteur / Intervenant')
    answer_location = fields.Char(
        string='Localisation',
        help="Coordonnées GPS ou description du lieu",
    )

    # ─── Scoring ──────────────────────────────────────────────────────────────
    score = fields.Float(string='Score', default=0.0)
    is_answered = fields.Boolean(
        string='Répondu', compute='_compute_is_answered', store=True,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Computed
    # ──────────────────────────────────────────────────────────────────────────

    @api.depends(
        'question_type',
        'answer_text', 'answer_date', 'answer_number',
        'answer_selection_id', 'answer_signature',
        'answer_barcode', 'answer_qrcode',
        'answer_author_id', 'answer_location',
    )
    def _compute_is_answered(self):
        for ans in self:
            t = ans.question_type
            ans.is_answered = bool(
                (t == 'text' and ans.answer_text)
                or (t == 'selection' and ans.answer_selection_id)
                or (t == 'date' and ans.answer_date)
                or (t == 'number' and ans.answer_number)
                or (t == 'formula')
                or (t == 'signature' and ans.answer_signature)
                or (t == 'barcode' and ans.answer_barcode)
                or (t == 'qrcode' and ans.answer_qrcode)
                or (t == 'author' and ans.answer_author_id)
                or (t == 'location' and ans.answer_location)
            )

    # ──────────────────────────────────────────────────────────────────────────
    # Onchanges – auto-scoring
    # ──────────────────────────────────────────────────────────────────────────

    @api.onchange('answer_selection_id')
    def _onchange_selection(self):
        if self.question_type == 'selection':
            self.score = self.answer_selection_id.score if self.answer_selection_id else 0.0

    @api.onchange('answer_text')
    def _onchange_text(self):
        if self.question_type == 'text':
            self.score = self.max_score if self.answer_text else 0.0

    @api.onchange('answer_date')
    def _onchange_date(self):
        if self.question_type == 'date':
            self.score = self.max_score if self.answer_date else 0.0

    @api.onchange('answer_number')
    def _onchange_number(self):
        if self.question_type == 'number':
            self.score = min(abs(self.answer_number), self.max_score)

    @api.onchange('answer_barcode')
    def _onchange_barcode(self):
        if self.question_type == 'barcode':
            self.score = self.max_score if self.answer_barcode else 0.0

    @api.onchange('answer_qrcode')
    def _onchange_qrcode(self):
        if self.question_type == 'qrcode':
            self.score = self.max_score if self.answer_qrcode else 0.0

    @api.onchange('answer_author_id')
    def _onchange_author(self):
        if self.question_type == 'author':
            self.score = self.max_score if self.answer_author_id else 0.0

    @api.onchange('answer_location')
    def _onchange_location(self):
        if self.question_type == 'location':
            self.score = self.max_score if self.answer_location else 0.0

    @api.onchange('answer_signature')
    def _onchange_signature(self):
        if self.question_type == 'signature':
            self.score = self.max_score if self.answer_signature else 0.0
