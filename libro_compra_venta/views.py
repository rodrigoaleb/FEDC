from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect, JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import  View, DetailView
from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView
from django.db.models import Q

from django_datatables_view.base_datatable_view import BaseDatatableView

from conectores.models import Compania

from facturas.models import Factura

from nota_credito.models import notaCredito

from nota_debito.models import notaDebito

from utils.utils import sendToSii
from utils.CustomMixin import SeleccionarEmpresaView

from .forms import *
from .models import *


class StartLibro(SeleccionarEmpresaView):
    """
    Selecciona la empresa

    @author Rodrigo A. Boet (rodrigo.b at timgla.com)
    @date 12-08-2019
    @version 1.0.0
    """

    def post(self, request, *args, **kwargs):

        empresa = int(request.POST.get('empresa'))
        print (self.kwargs['tipo'])
        if not empresa:
            return HttpResponseRedirect('/')
        empresa_obj = Compania.objects.get(pk=empresa)
        if empresa_obj and self.request.user == empresa_obj.owner and self.kwargs['tipo'] == 'crear':
            return HttpResponseRedirect(reverse_lazy('libro:crear_libro', kwargs={'pk':empresa}))
        elif empresa_obj and self.request.user == empresa_obj.owner and self.kwargs['tipo'] == 'listar':
            return HttpResponseRedirect(reverse_lazy('libro:listar_libro', kwargs={'pk':empresa}))
        else:
            return HttpResponseRedirect('/')


class CreateLibro(LoginRequiredMixin, FormView):
    """
    Registra un nuevo libro

    @author Rodrigo A. Boet (rodrigo.b at timgla.com)
    @date 12-08-2019
    @version 1.0.0
    """
    form_class = FormLibro
    template_name = 'crear_libro.html'
    success_url = '/libro/'
    model = Libro
    model_factura = Factura
    model_nota_cr = notaCredito
    model_nota_db = notaDebito

    def get_context_data(self, *args, **kwargs): 

        context = super().get_context_data(*args, **kwargs)

        context['compania'] = self.kwargs['pk']
        return context

    def form_valid(self, form, *args, **kwargs):
        
        compania = self.kwargs['pk']
        date = form['current_date'].value()
        date_arr = date.split('/')
        
        start_date = date_arr[2]+"-"+date_arr[1]+"-"+'01'
        objeto_datetime = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        start_date = objeto_datetime - relativedelta(months=1)
        end_date = objeto_datetime - timedelta(days=1)  # Resta a fecha actual 1 día
        #print(objeto_datetime, start_date)
        #date_arr.reverse()
        #end_date = "-".join(date_arr)

        objects = []
        factura = self.model_factura.objects.filter(compania=compania, fecha__range=[start_date, end_date])
        nota_credito = self.model_nota_cr.objects.filter(compania=compania, fecha__range=[start_date, end_date])
        nota_debito = self.model_nota_db.objects.filter(compania=compania, fecha__range=[start_date, end_date])
        
        for fact in factura:
            fact.doc_type = 33
            fact.total_doc = 1
            fact.numero_factura = fact.numero_factura.replace('º','')
        for fact in nota_debito:
            fact.doc_type = 56
            fact.total_doc = 1
            fact.numero_factura = fact.numero_factura.replace('º','')
        for fact in nota_credito:
            fact.doc_type = 61
            fact.total_doc = 1
            fact.numero_factura = fact.numero_factura.replace('º','')
        objects.append(factura)
        objects.append(nota_debito)
        objects.append(nota_credito)
        detail = form['details'].value()
        if detail:
            xml = render_to_string('xml_lcv/resumen_periodo.xml', {'objects':objects, 'objects_details': objects})
        else:
            xml = render_to_string('xml_lcv/resumen_periodo.xml', {'objects':objects})
        if not factura and not nota_debito and not nota_credito:
            messages.warning(self.request, "No existen facturas, notas de credito o debito para esta fecha {0}/{1}".format(start_date, end_date))
            return HttpResponseRedirect(reverse_lazy('libro:crear_libro', kwargs={'pk':compania}))

        try:
            compania = Compania.objects.get(pk=compania)    
            libro = self.model(
                fk_compania=compania,
                current_date=end_date,
                details=form['details'].value(),
                libro_xml=xml
                )
            libro.save()
            messages.success(self.request, "Se registro el libro con éxito")
        except Exception as e:
            compania = Compania.objects.get(pk=compania)
            messages.error(self.request, e)

        return HttpResponseRedirect(reverse_lazy('libro:listar_libro', kwargs={'pk':compania.pk}))


class ListarLibrosViews(LoginRequiredMixin, TemplateView):
    """
    Lista los libros

    @author Rodrigo A. Boet (rodrigo.b at timgla.com)
    @date 12-08-2019
    @version 1.0.0
    """
    template_name = 'listar_libro.html'


class AjaxListTable(LoginRequiredMixin, BaseDatatableView):
    """!
    Prepara la data para mostrar en el datatable

    @author Rodrigo A. Boet (rodrigo.b at timgla.com)
    @date 12-08-2019
    @version 1.0.0
    """
    # The model we're going to show
    model = Libro
    columns = ['current_date', 'details', 'libro_xml', 'enviada']
    # define column names that will be used in sorting
    # order is important and should be same as order of columns
    # displayed by datatables. For non sortable columns use empty
    # value like ''
    order_columns = ['-current_date', 'details', 'libro_xml']
    # set max limit of records returned, this is used to protect our site if someone tries to attack our site
    # and make it return huge amount of data
    max_display_length = 500


    def __init__(self):
        super(AjaxListTable, self).__init__()

    def get_initial_queryset(self):
        """!
        Consulta el modelo Intercambio

        @return: Objeto de la consulta
        """
        # return queryset used as base for futher sorting/filtering
        # these are simply objects displayed in datatable
        # You should not filter data returned here by any filter values entered by Intercambio. This is because
        # we need some base queryset to count total number of records.
        print(self.kwargs['pk'])
        return self.model.objects.filter(fk_compania=self.kwargs['pk']).order_by('-current_date')

    def filter_queryset(self, qs):
        # use parameters passed in GET request to filter queryset

        search = self.request.GET.get(u'search[value]', None)
        if search:
            qs_params = None
            if search in "Si" or search in "si":
                search = True
            elif search in "No" or search in "no":
                search = False
            q = Q(pk__istartswith=search)|Q(current_date__icontains=search)|Q(details__icontains=search)|Q(libro_xml__icontains=search)
            qs_params = qs_params | q if qs_params else q
            qs = qs.filter(qs_params)
        return qs

    def prepare_results(self, qs):
        """!
        Prepara la data para mostrar en el datatable
        @return: Objeto json con los datos del intercambio
        """
        # prepare list with output column data
        json_data = []
        for item in qs:
            
            detail = "Si" if item.details else "No"
            
            ver = "<a data-toggle='modal' data-target='#myModal' \
                    class='btn btn-block btn-info btn-xs fa fa-search' \
                    onclick='modal_detalle_libro({0})'></a>\
                    ".format(str(item.pk))
            if not item.enviada:
                send = "<a  class='btn btn-block btn-success btn-xs fa fa-paper-plane' onclick='enviar_libro({0})'></a>\
                    ".format(str(item.pk))
            else:
                send = ""
            json_data.append([
                item.current_date.strftime("%Y-%m-%d"),
                detail,
                item.libro_xml,
                ver + send,
                
            ])
            
        return json_data


class LibroDetailView(LoginRequiredMixin, DetailView):
  """
  Clase para el detalle de intercambio
  @author Rodrigo A. Boet (rodrigo.b at timgla.com)
  @copyright TIMG
  @date 12-08-2019
  @version 1.0
  """

  template_name="libro_detail.html"
  model = Libro

@method_decorator(csrf_exempt, name='dispatch')
class LibroSendView(LoginRequiredMixin,View):
    def post(self,request,pk):
        try:
            libro = Libro.objects.get(pk=pk)
            signed_xml = libro.sign_base('VENTA','MENSUAL','TOTAL')
            compania = libro.fk_compania
            send_sii = sendToSii(compania,signed_xml,compania.pass_certificado)
            if(not send_sii['estado']):
                print(send_sii['msg'])
                return JsonResponse({'success':False,'message':send_sii['msg']})
            else:
                print(send_sii['track_id'])
                return JsonResponse({'success':True,'message':'Libro envíado con éxito'})
        except Exception as e:
            print(e)
            return JsonResponse({'success':False,'message':'Libro incorrecto'})

