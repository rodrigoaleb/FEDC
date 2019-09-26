import json
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic.base import TemplateView

from django_datatables_view.base_datatable_view import BaseDatatableView
from django_weasyprint import WeasyTemplateResponseMixin

from facturas.models import Factura

from utils.utils import validarModelPorDoc, nombreTimbrePorDoc
from utils.views import (
    sendToSii, LoginRequeridoPerAuth
)
from .constants import NOMB_DOC, LIST_DOC


class SendToSiiView(LoginRequeridoPerAuth, View):
    """!
    Envia el documento al sii

    @author Rodrigo Boet (rudmanmrrod at gmail.com)
    @date 24-09-2019
    @version 1.0.0
    """
    group_required = [u"Super Admin", u"Admin", u"Invitado"]

    def get(self, request, **kwargs):
        """
        Método para manejar la petición post
        """
        print(kwargs['pk'])
        print(kwargs['dte'])
        model, url = validarModelPorDoc(kwargs['dte'])
        model = model.objects.get(pk=kwargs['pk'])
        send_sii = sendToSii(model.compania,model.dte_xml,model.compania.pass_certificado)
        if(not send_sii['estado']):
            return JsonResponse({'status':send_sii['estado'], 'msg':send_sii['msg']})
        else:
            model.track_id = send_sii['track_id']
            model.save()
            return JsonResponse({'status':send_sii['estado'], 'msg':'Envíado con éxito'})


class AjaxGenericListDTETable(LoginRequiredMixin, BaseDatatableView):
    """!
    Prepara la data para mostrar en el datatable

    @author Rodrigo A. Boet (rodrigo.b at timgla.com)
    @date 19-09-2019
    @version 1.0.0
    """
    # The model we're going to show
    model = Factura
    columns = ['pk', 'numero_factura', 'compania', 'n_folio']
    # define column names that will be used in sorting
    # order is important and should be same as order of columns
    # displayed by datatables. For non sortable columns use empty
    # value like ''
    order_columns = ['pk', 'numero_factura', 'compania', 'n_folio']
    # set max limit of records returned, this is used to protect our site if someone tries to attack our site
    # and make it return huge amount of data
    max_display_length = 500


    def __init__(self):
        super(AjaxGenericListDTETable, self).__init__()

    def get_initial_queryset(self):
        """!
        Consulta el modelo Intercambio

        @return: Objeto de la consulta
        """
        # return queryset used as base for futher sorting/filtering
        # these are simply objects displayed in datatable
        # You should not filter data returned here by any filter values entered by Intercambio. This is because
        # we need some base queryset to count total number of records.
        tipo_doc = self.kwargs['dte']
        self.model, url = validarModelPorDoc(tipo_doc)
        if self.request.GET.get(u'sistema', None) == 'True':
            return self.model.objects.filter(compania=self.kwargs['pk'], track_id=None)
        return self.model.objects.filter(compania=self.kwargs['pk']).exclude(track_id=None)

    def filter_queryset(self, qs):
        # use parameters passed in GET request to filter queryset

        search = self.request.GET.get(u'search[value]', None)
        if search:
            qs_params = None
            q = Q(pk__istartswith=search)|Q(compania__razon_social__icontains=search)|Q(n_folio__icontains=search)|Q(numero_factura__icontains=search)
            qs_params = qs_params | q if qs_params else q
            qs = qs.filter(qs_params)
        return qs

    def prepare_results(self, qs):
        """!
        Prepara la data para mostrar en el datatable
        @return: Objeto json con los datos del DTE
        """
        # prepare list with output column data
        json_data = []
        for item in qs:
            if self.request.GET.get(u'sistema', None) == 'True':
                url = str(reverse_lazy('base:send_sii', kwargs={'pk':item.pk, 'dte':self.kwargs['dte']}))
                boton_enviar_sii = '<a href="#" onclick=send_to_sii("'+url+'")\
                                    class="btn btn-success">Enviar al Sii</a> '
                botones_acciones = boton_enviar_sii
            else:
                boton_estado = '<a href="{0}"\
                                class="btn btn-success">Ver Estado</a> '.format(reverse_lazy('notaCredito:ver_estado_nc', kwargs={'pk':self.kwargs['pk'], 'slug':item.numero_factura}))
                boton_imprimir_doc = '<a  id="edit_foo" href="{0}"\
                                     target="_blank" class="btn btn-info">Imprimir</a> '.format(reverse_lazy('base:imprimir_factura', kwargs={'pk':self.kwargs['pk'], 'slug':item.numero_factura, 'doc':'NOTA_CRE_ELEC'}))
                boton_imprimir_con = '<a  id="edit_foo" href="{0}?impre=cont"\
                                     target="_blank" class="btn btn-warning">Impresion continua</a>'.format(reverse_lazy('base:imprimir_factura', kwargs={'pk':self.kwargs['pk'], 'slug':item.numero_factura, 'doc':'NOTA_CRE_ELEC'}))
                botones_acciones = boton_estado + boton_imprimir_doc + boton_imprimir_con
            json_data.append([
                item.numero_factura,
                item.compania.razon_social,
                item.n_folio,
                botones_acciones
            ])
        return json_data

class ImprimirFactura(LoginRequiredMixin, TemplateView, WeasyTemplateResponseMixin):
    """!
    Class para imprimir la factura en PDF

    @author Rodrigo Boet (rudmanmrrod at gmail.com)
    @date 21-03-2019
    @version 1.0.0
    """
    template_name = "pdf/factura.pdf.html"
    model = Factura

    def dispatch(self, request, *args, **kwargs):
        num_factura = self.kwargs['slug']
        compania = self.kwargs['pk']
        tipo_doc = self.kwargs['doc']
        impre_cont = request.GET.get('impre')

        if impre_cont == 'cont':
            self.template_name = "pdf/impresion.continua.pdf.html"
        if tipo_doc in LIST_DOC:
            self.model, url = validarModelPorDoc(tipo_doc)
            try:
                factura = self.model.objects.select_related().get(numero_factura=num_factura, compania=compania)
                return super().dispatch(request, *args, **kwargs)
            except Exception as e:
                print(e)
                factura = self.model.objects.select_related().filter(numero_factura=num_factura, compania=compania)
                if len(factura) > 1:
                    messages.error(self.request, 'Existe mas de un registro con el mismo numero de factura: {0}'.format(num_factura))
                    return redirect(reverse_lazy(url, kwargs={'pk': compania}))
                else:
                    messages.error(self.request, "No se encuentra registrada esta factura: {0}".format(str(num_factura)))
                    return redirect(reverse_lazy(url, kwargs={'pk': compania}))
        else:
            messages.error(self.request, "No existe este tipo de documento: {0}".format(str(tipo_doc)))
            return redirect(reverse_lazy(url, kwargs={'pk': compania}))

    def get_context_data(self, *args, **kwargs):
        """!
        Method to handle data on get

        @date 21-03-2019
        @return Returns dict with data
        """
        context = super().get_context_data(*args, **kwargs)
        num_factura = self.kwargs['slug']
        compania = self.kwargs['pk']
        tipo_doc = self.kwargs['doc']
        
        context['factura'] = self.model.objects.select_related().get(numero_factura=num_factura, compania=compania)
        context['nombre_documento'] = NOMB_DOC[tipo_doc]
        etiqueta=self.kwargs['slug'].replace('º','')
        context['etiqueta'] = etiqueta
        
        prod = context['factura'].productos.replace('\'{','{').replace('}\'','}').replace('\'',"\"")

        productos = json.loads(prod)
        context['productos'] = productos
        nombre_timbre = nombreTimbrePorDoc(self.kwargs['doc'])
        ruta = settings.STATIC_URL +nombre_timbre+'/'+etiqueta+'/timbre.jpg'
        context['ruta']=ruta
        return context
