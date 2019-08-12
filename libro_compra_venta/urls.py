from django.urls import path

from .views import *

app_name = 'libro'

urlpatterns = [
    path('libro/', StartLibro.as_view(),name='libro'),
    path('libro/crear/<int:pk>', CreateLibro.as_view(),name='crear_libro'),
    path('libro/listar/<int:pk>', ListarLibrosViews.as_view(),name='listar_libro'),
    path('libro/listar-ajax/<int:pk>', AjaxListTable.as_view(),name='listar_libro_ajax'),
]