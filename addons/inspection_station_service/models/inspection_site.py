# -*- coding: utf-8 -*-
from odoo import api, fields, models


class InspectionSite(models.Model):
    _name = 'inspection.site'
    _description = "Site d'inspection"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Nom du site', required=True, tracking=True,
        help="Nom complet de la station ou du site à inspecter",
    )
    code = fields.Char(
        string='Code', required=True, copy=False, tracking=True,
        help="Code unique identifiant le site",
    )
    site_type = fields.Selection([
        ('station', 'Station Service'),
        ('depot', 'Dépôt'),
        ('agence', 'Agence'),
        ('autre', 'Autre'),
    ], string='Type de site', default='station', required=True, tracking=True)

    address = fields.Text(string='Adresse')
    city = fields.Char(string='Ville')
    zip_code = fields.Char(string='Code postal')
    country_id = fields.Many2one('res.country', string='Pays')
    latitude = fields.Float(string='Latitude', digits=(10, 7))
    longitude = fields.Float(string='Longitude', digits=(10, 7))

    manager_id = fields.Many2one(
        'res.users', string='Responsable du site', tracking=True,
    )
    phone = fields.Char(string='Téléphone')
    email = fields.Char(string='Email')

    active = fields.Boolean(string='Actif', default=True)
    notes = fields.Text(string='Notes / Observations')

    inspection_count = fields.Integer(
        string='Nombre d\'inspections',
        compute='_compute_inspection_count',
    )

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Le code du site doit être unique !'),
    ]

    def _compute_inspection_count(self):
        Report = self.env['inspection.report']
        for site in self:
            site.inspection_count = Report.search_count([('site_id', '=', site.id)])

    def action_view_inspections(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Inspections de %s" % self.name,
            'res_model': 'inspection.report',
            'view_mode': 'list,form',
            'domain': [('site_id', '=', self.id)],
            'context': {'default_site_id': self.id},
        }
