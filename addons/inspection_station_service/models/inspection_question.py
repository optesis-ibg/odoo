# -*- coding: utf-8 -*-
from odoo import api, fields, models


QUESTION_TYPES = [
    ('text', 'Texte libre'),
    ('selection', 'Sélection / QCM'),
    ('date', 'Date'),
    ('number', 'Nombre'),
    ('formula', 'Formule de calcul'),
    ('signature', 'Signature'),
    ('barcode', 'Code barre'),
    ('qrcode', 'QR Code'),
    ('author', 'Auteur / Intervenant'),
    ('location', 'Localisation'),
]


class InspectionQuestion(models.Model):
    _name = 'inspection.question'
    _description = "Question d'inspection"
    _order = 'template_id, sequence, id'

    name = fields.Char(
        string='Intitulé de la question', required=True,
        help="Texte complet de la question posée à l'inspecteur",
    )
    description = fields.Text(
        string='Description / Aide',
        help="Précisions ou instructions pour répondre à cette question",
    )
    question_type = fields.Selection(
        QUESTION_TYPES,
        string='Type de réponse', required=True, default='text',
    )
    sequence = fields.Integer(string='Séquence', default=10)
    template_id = fields.Many2one(
        'inspection.template', string='Modèle', ondelete='cascade',
    )
    category = fields.Char(
        string='Catégorie',
        help="Regroupe les questions par thème pour le graphique radar",
    )

    # Scoring
    max_score = fields.Float(
        string='Score maximum', default=10.0,
        help="Score maximal attribuable à cette question",
    )
    required = fields.Boolean(
        string='Obligatoire', default=False,
        help="La réponse à cette question est obligatoire pour valider l'inspection",
    )

    # Options for 'selection' type
    option_ids = fields.One2many(
        'inspection.question.option', 'question_id',
        string='Options de réponse',
    )

    # Formula for 'formula' type
    formula = fields.Text(
        string='Formule',
        help=(
            "Formule de calcul du score. "
            "Utilisez les codes des questions comme variables. "
            "Exemple : Q1 + Q2 * 0.5, ou (Q3 / Q4) * 10"
        ),
    )

    # Display hint for inspectors
    @api.onchange('question_type')
    def _onchange_question_type(self):
        if self.question_type == 'formula':
            self.max_score = 0.0


class InspectionQuestionOption(models.Model):
    _name = 'inspection.question.option'
    _description = "Option de réponse"
    _order = 'question_id, sequence, id'

    question_id = fields.Many2one(
        'inspection.question', string='Question',
        ondelete='cascade', required=True,
    )
    name = fields.Char(string='Option', required=True)
    score = fields.Float(string='Score attribué', default=0.0)
    sequence = fields.Integer(string='Séquence', default=10)
    color = fields.Char(
        string='Couleur',
        help="Couleur CSS (#hex ou nom) pour visualisation",
        default='#6c757d',
    )
