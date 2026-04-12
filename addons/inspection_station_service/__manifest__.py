# -*- coding: utf-8 -*-
{
    'name': 'Inspection Station Service',
    'version': '14.0.1.0.0',
    'category': 'Operations/Quality',
    'summary': 'Inspection de station service avec scoring et tableaux de bord',
    'description': """
Inspection Station Service
==========================
Application complète d'inspection de station service avec :

* Score par question et score global en pourcentage
* Types de réponse : texte libre, sélection, date, nombre, formule de calcul,
  signature, code barre, QR Code, auteur/intervenant, localisation
* Création de questions et modèles d'inspection personnalisés
* Configuration des sites (stations service)
* Tableau de bord avec graphiques :
  - Camembert (distribution des scores)
  - Colonnes (score par site)
  - Araignée / Radar (score par catégorie)
  - Courbe de tendance mensuelle
    """,
    'author': 'Optesis IBG',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/inspection_site_views.xml',
        'views/inspection_template_views.xml',
        'views/inspection_report_views.xml',
        'views/inspection_dashboard_views.xml',
        'views/menus.xml',
    ],
    'qweb': [
        'static/src/xml/inspection_dashboard.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
