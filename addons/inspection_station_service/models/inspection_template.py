# -*- coding: utf-8 -*-
from odoo import api, fields, models


class InspectionTemplate(models.Model):
    _name = 'inspection.template'
    _description = "Modèle d'inspection"
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(
        string='Nom du modèle', required=True, tracking=True,
    )
    code = fields.Char(
        string='Code référence',
        help="Code court unique pour identifier le modèle",
    )
    description = fields.Text(string='Description')

    site_ids = fields.Many2many(
        'inspection.site',
        'inspection_template_site_rel',
        'template_id', 'site_id',
        string='Sites applicables',
        help="Sites pour lesquels ce modèle d'inspection est utilisé",
    )

    question_ids = fields.One2many(
        'inspection.question', 'template_id',
        string='Questions',
        copy=True,
    )

    active = fields.Boolean(string='Actif', default=True)

    total_max_score = fields.Float(
        string='Score maximum total',
        compute='_compute_total_max_score',
        store=True,
        help="Somme des scores maximaux de toutes les questions",
    )
    question_count = fields.Integer(
        string='Nombre de questions',
        compute='_compute_question_count',
    )
    report_count = fields.Integer(
        string='Rapports générés',
        compute='_compute_report_count',
    )

    @api.depends('question_ids.max_score', 'question_ids.question_type')
    def _compute_total_max_score(self):
        for template in self:
            template.total_max_score = sum(
                q.max_score for q in template.question_ids
                if q.question_type != 'formula'
            )

    def _compute_question_count(self):
        for template in self:
            template.question_count = len(template.question_ids)

    def _compute_report_count(self):
        Report = self.env['inspection.report']
        for template in self:
            template.report_count = Report.search_count(
                [('template_id', '=', template.id)]
            )

    def action_view_reports(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Rapports – %s" % self.name,
            'res_model': 'inspection.report',
            'view_mode': 'list,form',
            'domain': [('template_id', '=', self.id)],
            'context': {'default_template_id': self.id},
        }
