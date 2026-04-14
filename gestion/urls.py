from django.urls import path
from . import views

urlpatterns = [
    # Accueil et Dashboard
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # Authentification
    path('inscription/', views.signup, name='signup'),
    path('inventaire/verif/', views.verifier_patron_inventaire, name='verifier_patron_inventaire'),

    # Gestion des Produits (CRUD)
    path('produits/', views.liste_produits, name='liste_produits'),
    path('produits/ajouter/', views.ajouter_produit, name='ajouter_produit'),
    path('produits/modifier/<int:pk>/', views.modifier_produit, name='modifier_produit'),
    path('produits/supprimer/<int:pk>/', views.supprimer_produit, name='supprimer_produit'),

    # Gestion des Catégories
    path('categories/', views.liste_categories, name='liste_categories'),
    path('categories/ajouter/', views.ajouter_categorie, name='ajouter_categorie'),
    path('categories/modifier/<int:pk>/', views.modifier_categorie, name='modifier_categorie'),
    path('categories/supprimer/<int:pk>/', views.supprimer_categorie, name='supprimer_categorie'),

    # Système de Vente et POS
    path('vente/', views.page_vente, name='page_vente'),
    path('vente/valider/', views.valider_vente, name='valider_vente'),
    path('vente/succes/<int:vente_id>/', views.succes_vente, name='succes_vente'),
    path('vente/recu/<int:vente_id>/', views.generer_recu_pdf, name='generer_recu_pdf'),

    # API pour les détails des produits (AJAX)
    path('api/produit/<int:pk>/', views.get_produit_details, name='get_produit_details'),

    # Utilitaires et Export
    path('exporter/csv/', views.exporter_csv, name='exporter_csv'),
    path('exporter/pdf/', views.exporter_pdf, name='exporter_pdf'),

    # Historique et Notifications
    path('historique/', views.historique_stock, name='historique_stock'),
    path('notifications/', views.liste_notifications, name='liste_notifications'),
    path('notifications/supprimer/<int:notif_id>/', views.supprimer_notification, name='supprimer_notification'),
    path('notifications/marquer-lu/<int:notif_id>/', views.marquer_notification_lue, name='marquer_notification_lue'),

    path('statistiques/', views.statistiques, name='statistiques'),
    path('rapports/ventes/', views.rapport_ventes, name='rapport_ventes'),
    path('produits/', views.liste_produits, name='liste_produits'),
    path('produits/export/csv/', views.exporter_csv, name='exporter_csv'),
    path('valider-vente/', views.valider_vente, name='valider_vente'),
    path('recu/<int:vente_id>/', views.succes_vente, name='recu_vente'),

]