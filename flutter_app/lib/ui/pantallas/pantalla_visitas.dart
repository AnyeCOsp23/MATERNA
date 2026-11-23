/// Pestaña «Mapa y visitas»: dónde están las gestantes de esta cuenta y a quién visitar primero.
///
/// Filtros por nivel y por estado (Pendientes, Visitadas, Todas), que se aplican al mapa y a la lista a la vez.
/// Las pendientes se ordenan por prioridad (una tarjeta por gestante: riesgo y tiempo sin contacto) o como
/// recorrido (paradas por lugar, dibujadas en el mapa desde la cabecera del municipio de la cuenta). Cada gestante
/// se marca con ✓ como visitada (se puede devolver a pendientes) o, en su detalle, como «No la encontramos».
/// Las distancias son en línea recta y solo de apoyo: no cambian el resultado.
library;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart' show RenderAbstractViewport;

import '../../datos/base_local.dart';
import '../../datos/ubicaciones.dart';
import '../../motor/geografia.dart';
import '../../motor/recursos.dart';
import '../../motor/visitas.dart';
import '../tema/tema_materna.dart';
import '../widgets/barra_flotante.dart';
import '../widgets/encabezado.dart';
import '../widgets/iconos_trazo.dart';
import '../widgets/mapa_materna.dart';

String kmLegible(double km) => km < 10 ? km.toStringAsFixed(1).replaceAll('.', ',') : km.round().toString();

String haceCuanto(DateTime fecha, {DateTime? ahora}) {
  final dias = (ahora ?? DateTime.now()).difference(fecha).inDays;
  return dias <= 0
      ? 'hoy'
      : dias == 1
      ? 'hace 1 día'
      : 'hace $dias días';
}

String _plural(int n, String uno, String varios) => '$n ${n == 1 ? uno : varios}';

enum FiltroEstado { pendientes, visitadas, todas }

class PantallaVisitas extends StatefulWidget {
  const PantallaVisitas({super.key, required this.recursos, required this.base, required this.perfil, required this.cambios});

  final RecursosMaterna recursos;
  final BaseLocal base;
  final Perfil perfil;

  /// Aumenta cuando se guarda una evaluación o una visita: la pantalla se recarga sola.
  final ValueNotifier<int> cambios;

  @override
  State<PantallaVisitas> createState() => _EstadoVisitas();
}

class _EstadoVisitas extends State<PantallaVisitas> {
  int? _clase;
  var _estado = FiltroEstado.pendientes;
  var _recorrido = false;
  int? _abierta;

  /// Zona elegida en el mapa (un lugar o un grupo de lugares): la lista muestra solo sus gestantes. No cambia
  /// ningún número (conteos, orden, recorrido): esos siempre salen de todas las gestantes.
  ({String nombre, Set<String> claves})? _zona;
  final _anclaZona = GlobalKey();

  /// Cabeceras (paradas del recorrido) desplegadas y las que muestran todas sus gestantes.
  final _paradasAbiertas = <String>{};
  final _paradasCompletas = <String>{};

  /// Las que abrió la zona elegida (se vuelven a plegar al quitarla).
  final _abiertasPorZona = <String>{};
  final _anclasParada = <String, GlobalKey>{};

  final _desplazamiento = ScrollController();
  final _controlMapa = ControlMapaMaterna();
  late Future<List<RegistroUbicacion>> _datos = _cargar();

  /// Alto del mapa fijo arriba (el mapa y su margen).
  static const _altoMapa = 320.0, _altoMapaFijo = _altoMapa + 18;

  /// Una cabecera muestra primero estas gestantes; el resto, con «Ver las N gestantes».
  static const _primeras = 5;

  @override
  void initState() {
    super.initState();
    widget.cambios.addListener(_recargar);
  }

  @override
  void dispose() {
    widget.cambios.removeListener(_recargar);
    _desplazamiento.dispose();
    super.dispose();
  }

  Future<List<RegistroUbicacion>> _cargar() => widget.base.listarUbicaciones(perfil: widget.perfil);

  void _recargar() => setState(() {
    _datos = _cargar();
  });

  bool _pasaEstado(RegistroUbicacion u, [FiltroEstado? estado]) => switch (estado ?? _estado) {
    FiltroEstado.pendientes => u.estado != EstadoVisita.visitada,
    FiltroEstado.visitadas => u.estado == EstadoVisita.visitada,
    FiltroEstado.todas => true,
  };

  bool _enZona(Visita v) => _zona == null || _zona!.claves.contains(v.clave);

  Future<void> _marcar(Visita v, EstadoVisita estado) async {
    final u = v.ubicacion;
    await widget.base.marcarVisita(u.id, estado, perfil: widget.perfil);
    if (!mounted) return;
    final mensaje = switch (estado) {
      EstadoVisita.visitada => 'Visita registrada.',
      EstadoVisita.sinLocalizar => 'Marcada como «no la encontramos»: sigue en pendientes.',
      EstadoVisita.pendiente => 'Devuelta a pendientes.',
    };
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(mensaje),
          // con una acción, Flutter deja el aviso fijo por defecto: este se va solo a los 5 s
          duration: const Duration(seconds: 5),
          persist: false,
          action: SnackBarAction(
            label: 'Deshacer',
            onPressed: () async {
              await widget.base.restaurarVisita(u.id, u.estado, u.ultimoContacto, perfil: widget.perfil);
              widget.cambios.value++;
            },
          ),
        ),
      );
    setState(() => _abierta = null);
    widget.cambios.value++;
  }

  /// Lleva la lista hasta [ancla], justo debajo del mapa fijo (el cálculo del viewport ya descuenta el mapa fijo).
  /// [espera]: lo que tarda en abrirse lo que se acaba de desplegar, para que la lista ya tenga su alto final.
  void _revelar(GlobalKey ancla, {Duration espera = Duration.zero}) async {
    if (espera > Duration.zero && !MediaQuery.of(context).disableAnimations) await Future<void>.delayed(espera);
    if (!mounted) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final objeto = ancla.currentContext?.findRenderObject();
      if (objeto == null || !mounted || !_desplazamiento.hasClients) return;
      final posicion = _desplazamiento.position;
      final destino = (RenderAbstractViewport.of(objeto).getOffsetToReveal(objeto, 0).offset - 8).clamp(
        posicion.minScrollExtent,
        posicion.maxScrollExtent,
      );
      if (MediaQuery.of(context).disableAnimations) {
        _desplazamiento.jumpTo(destino);
      } else {
        _desplazamiento.animateTo(destino, duration: const Duration(milliseconds: 400), curve: Curves.easeInOutCubic);
      }
    });
  }

  /// Elegir una zona en el mapa: la lista se filtra a sus gestantes (sus cabeceras, desplegadas) y baja hasta el aviso.
  void _elegirZona(String nombre, List<PuntoMapa> lugares) {
    setState(() {
      _quitarZona();
      _zona = (nombre: nombre, claves: {for (final p in lugares) p.clave});
      _abiertasPorZona.addAll(_zona!.claves.difference(_paradasAbiertas));
      _paradasAbiertas.addAll(_abiertasPorZona);
      _abierta = null;
    });
    _revelar(_anclaZona);
  }

  /// Abrir o cerrar una cabecera; al abrirla, el mapa vuela a ese lugar y la lista la deja a la vista.
  void _alternarParada(Parada p) {
    final abrir = !_paradasAbiertas.contains(p.clave);
    setState(() => abrir ? _paradasAbiertas.add(p.clave) : _paradasAbiertas.remove(p.clave));
    if (abrir) {
      _controlMapa.enfocar(p.clave);
      _revelar(_anclasParada.putIfAbsent(p.clave, GlobalKey.new), espera: const Duration(milliseconds: 280));
    }
  }

  void _quitarZona() {
    _paradasAbiertas.removeAll(_abiertasPorZona);
    _abiertasPorZona.clear();
    _zona = null;
  }

  void _cambiar(VoidCallback cambio) => setState(() {
    cambio();
    _abierta = null;
  });

  @override
  Widget build(BuildContext context) {
    final geo = widget.recursos.geografia;
    return SafeArea(
      bottom: false,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: FutureBuilder<List<RegistroUbicacion>>(
            future: _datos,
            builder: (context, estado) {
              final arriba = <Widget>[
                const EncabezadoMaterna(etiqueta: 'En territorio'),
                const SizedBox(height: 14),
                TituloConIcono(
                  icono: IconoDeTrazo(IconoTrazo.mapa, color: ColoresMaterna.ciruela900, tamano: 26),
                  titulo: 'Mapa y visitas',
                  subtitulo: 'Dónde están sus gestantes y a quién visitar primero',
                ),
                const SizedBox(height: 14),
              ];
              final listo = geo != null && estado.connectionState == ConnectionState.done && (estado.data ?? const []).isNotEmpty;
              final partes = listo ? _contenido(estado.data!, geo) : null;
              return CustomScrollView(
                controller: _desplazamiento,
                // la lista se arma unos cuantos cientos de píxeles por delante: lo que se pide mostrar ya existe
                cacheExtent: 1500,
                slivers: [
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                    sliver: SliverList.list(
                      children: [
                        ...arriba,
                        if (geo == null)
                          const Text('El mapa no está disponible en este dispositivo.')
                        else if (estado.connectionState != ConnectionState.done)
                          const Center(
                            child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()),
                          )
                        else if (!listo)
                          Padding(
                            padding: const EdgeInsets.all(24),
                            child: Text(
                              'Aún no hay gestantes con ubicación. Regístrela en el paso «Contexto y atención» del triaje '
                              '(«Ubicación para la visita») o con la carga de la IPS.',
                              key: const Key('visitas-vacio'),
                              textAlign: TextAlign.center,
                              style: TextStyle(color: ColoresMaterna.tintaSuave),
                            ),
                          )
                        else
                          ...partes!.antes,
                      ],
                    ),
                  ),
                  if (partes != null) ...[
                    // el mapa queda fijo arriba mientras se recorre la lista (como en el mockup)
                    SliverPersistentHeader(
                      pinned: true,
                      delegate: _MapaFijo(alto: _altoMapaFijo, mapa: partes.mapa),
                    ),
                    SliverPadding(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, BarraFlotante.espacioInferior),
                      sliver: SliverList.list(children: partes.despues),
                    ),
                  ],
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  ({List<Widget> antes, Widget mapa, List<Widget> despues}) _contenido(List<RegistroUbicacion> datos, Geografia geo) {
    // UNA sola fuente para todos los números: todas las gestantes con los filtros de nivel y estado. La zona elegida
    // en el mapa solo decide qué tarjetas se ven (conservan su número de orden).
    final gestantes = unaPorGestante(datos);
    final enNivel = _clase == null ? gestantes : gestantes.where((u) => u.clase == _clase).toList();
    final visibles = enNivel.where(_pasaEstado).toList();
    final hechas = gestantes.where((u) => u.estado == EstadoVisita.visitada).length;
    final verOrden = _estado != FiltroEstado.visitadas;
    final municipioCuenta = geo.porNombre(widget.perfil.municipio);
    final inicio = municipioCuenta == null ? null : geo.cabecera(municipioCuenta.codigo)?.posicion;
    final prioridad = visitasPorPrioridad(visibles, geo);
    final recorrido = verOrden && _recorrido ? recorridoPorLugar(visibles, geo, inicio: inicio) : null;
    final zona = _zona;
    final enLaZona = zona == null ? null : visibles.where((u) => zona.claves.contains(claveLugar(u))).length;

    // nombres de las cabeceras de la zona, para orientarse
    final codigos = {
      for (final u in visibles) u.codigoMunicipio,
      if (recorrido != null && municipioCuenta != null) municipioCuenta.codigo,
    };
    final rotulos = <RotuloMapa>[
      for (final c in codigos)
        if (geo.cabecera(c) case final cab?) (posicion: cab.posicion, texto: geo.municipios[c]!.nombre),
    ];

    final antes = <Widget>[
      FiltroNivel(
        key: const Key('filtro-visitas'),
        seleccion: _clase,
        conteos: {
          null: gestantes.where(_pasaEstado).length,
          for (final c in [2, 1, 0]) c: gestantes.where((u) => u.clase == c && _pasaEstado(u)).length,
        },
        alCambiar: (c) => _cambiar(() => _clase = c),
      ),
      const SizedBox(height: 12),
      Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          for (final (f, nombre) in [
            (FiltroEstado.pendientes, 'Pendientes'),
            (FiltroEstado.visitadas, 'Visitadas'),
            (FiltroEstado.todas, 'Todas'),
          ])
            _ChipEstado(
              key: Key('estado-${f.name}'),
              texto: nombre,
              cuenta: enNivel.where((u) => _pasaEstado(u, f)).length,
              activo: _estado == f,
              alTocar: () => _cambiar(() => _estado = f),
            ),
        ],
      ),
      const SizedBox(height: 4),
    ];

    final mapa = MapaMaterna(
      // la clave no depende de la zona: al elegirla, el mapa conserva su zoom y su etiqueta
      key: ValueKey('mapa-visitas-$_clase-${_estado.name}-${recorrido != null}-${visibles.length}-$hechas'),
      geografia: geo,
      puntos: puntosDelMapa(visibles, geo),
      alto: _altoMapa,
      atenuarVisitadas: true,
      control: _controlMapa,
      ruta: recorrido == null
          ? null
          : RutaMapa(
              inicio: inicio,
              paradas: [
                for (final p in recorrido.paradas)
                  if (p.posicion != null) (clave: p.clave, posicion: p.posicion!, nivel: p.nivel),
              ],
            ),
      rotulos: rotulos,
      alElegirZona: _elegirZona,
    );

    final despues = <Widget>[
      LeyendaMapa(conVisitadas: _estado != FiltroEstado.pendientes, conRecorrido: recorrido != null),
      const SizedBox(height: 14),
      _Avance(hechas: hechas, total: gestantes.length),
      if (verOrden) ...[
        const SizedBox(height: 14),
        _SelectorOrden(recorrido: _recorrido, alCambiar: (r) => _cambiar(() => _recorrido = r)),
      ],
      if (zona != null) ...[
        const SizedBox(height: 12),
        _AvisoZona(key: _anclaZona, nombre: zona.nombre, gestantes: enLaZona!, alQuitar: () => _cambiar(_quitarZona)),
      ],
      const SizedBox(height: 10),
      ..._encabezadoLista(prioridad, recorrido),
      ..._lista(visibles, geo, prioridad, recorrido),
    ];
    return (antes: antes, mapa: mapa, despues: despues);
  }

  List<Widget> _encabezadoLista(List<Visita> prioridad, Recorrido? recorrido) {
    final suave = TextStyle(color: ColoresMaterna.tintaSuave, fontSize: 12.5, height: 1.4);
    if (_estado == FiltroEstado.visitadas) {
      return [Text('De la visita más reciente a la más antigua.', style: suave), const SizedBox(height: 10)];
    }
    if (recorrido == null) {
      final pendientes = prioridad.where(_enZona).length;
      return [
        Text('Ordenadas de mayor a menor riesgo; en cada nivel, primero la que lleva más tiempo sin contacto.', style: suave),
        if (pendientes > 0) ...[
          const SizedBox(height: 8),
          Text(
            _plural(pendientes, 'gestante pendiente', 'gestantes pendientes'),
            key: const Key('visitas-total'),
            style: TextStyle(fontWeight: FontWeight.w700, color: ColoresMaterna.tinta),
          ),
        ],
        const SizedBox(height: 10),
      ];
    }
    if (recorrido.paradas.isEmpty) return const [];
    final coincide =
        [for (final v in prioridad) v.ubicacion.id].join(',') == [for (final v in recorrido.visitas) v.ubicacion.id].join(',');
    final desde = recorrido.inicio == null ? 'Desde la primera parada.' : 'Desde la cabecera de ${widget.perfil.municipio}.';
    return [
      Container(
        key: const Key('resumen-recorrido'),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(color: ColoresMaterna.campo, borderRadius: BorderRadius.circular(14)),
        child: Row(
          children: [
            Icon(Icons.route_rounded, color: ColoresMaterna.ciruela900),
            const SizedBox(width: 10),
            Expanded(
              child: Text.rich(
                TextSpan(
                  children: [
                    TextSpan(
                      text:
                          '${_plural(recorrido.paradas.length, 'parada', 'paradas')} · ${kmLegible(recorrido.totalKm)} km en línea recta\n',
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    TextSpan(text: '$desde No son carreteras: el camino real será más largo.'),
                  ],
                ),
                style: TextStyle(color: ColoresMaterna.tinta, fontSize: 12.5, height: 1.4),
              ),
            ),
          ],
        ),
      ),
      if (coincide && prioridad.length > 1) ...[
        const SizedBox(height: 8),
        Container(
          key: const Key('recorrido-coincide'),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(color: estiloPorCategoria['Riesgo Medio']!.fondo, borderRadius: BorderRadius.circular(12)),
          child: Text(
            'En este grupo, el recorrido sale en el mismo orden que la prioridad.',
            style: TextStyle(color: estiloPorCategoria['Riesgo Medio']!.tinta, fontSize: 12),
          ),
        ),
      ],
      const SizedBox(height: 10),
    ];
  }

  List<Widget> _lista(List<RegistroUbicacion> visibles, Geografia geo, List<Visita> prioridad, Recorrido? recorrido) {
    final hechas = visitasHechas(visibles, geo).where(_enZona).toList();
    // con una zona elegida se muestran solo sus tarjetas, cada una con su número de orden de siempre
    final List<Widget> pendientes = recorrido != null
        ? [
            for (final (i, p) in recorrido.paradas.indexed)
              if (_zona == null || _zona!.claves.contains(p.clave)) _parada(p, i),
          ]
        : [
            for (final (i, v) in prioridad.indexed)
              if (_enZona(v)) _tarjeta(v, numero: i + 1, siguiente: i == 0),
          ];
    final visitadas = [for (final v in hechas) _tarjeta(v)];
    if (pendientes.isEmpty && visitadas.isEmpty ||
        (_estado == FiltroEstado.pendientes && pendientes.isEmpty) ||
        (_estado == FiltroEstado.visitadas && visitadas.isEmpty)) {
      final (titulo, texto) = switch (_estado) {
        FiltroEstado.pendientes => ('Todo al día', 'No quedan visitas pendientes con este filtro.'),
        FiltroEstado.visitadas => ('Aún sin visitas', 'Las gestantes que marque con ✓ aparecen aquí.'),
        FiltroEstado.todas => ('Sin gestantes', 'No hay gestantes con este filtro.'),
      };
      return [_Vacio(titulo: titulo, texto: texto)];
    }
    return switch (_estado) {
      FiltroEstado.pendientes => pendientes,
      FiltroEstado.visitadas => visitadas,
      FiltroEstado.todas => [
        if (pendientes.isNotEmpty) ...[_Seccion('Pendientes', prioridad.where(_enZona).length), ...pendientes],
        if (visitadas.isNotEmpty) ...[_Seccion('Visitadas', visitadas.length), ...visitadas],
      ],
    };
  }

  Widget _tarjeta(Visita v, {int? numero, bool siguiente = false}) {
    final u = v.ubicacion;
    return _TarjetaVisita(
      key: Key('visita-${u.id}'),
      visita: v,
      numero: numero,
      siguiente: siguiente,
      estilo: estiloPorCategoria[widget.recursos.clasificador.clases[u.clase]]!,
      seleccionada: _abierta == u.id,
      abierta: _abierta == u.id,
      alTocar: () => setState(() => _abierta = _abierta == u.id ? null : u.id),
      alMarcar: _marcar,
    );
  }

  /// Cabecera (parada del recorrido): plegada por defecto; al desplegarla muestra sus primeras gestantes y
  /// «Ver las N gestantes». Sin borde ni escala: es una tarjeta alta y no debe montarse sobre las vecinas.
  Widget _parada(Parada p, int i) {
    final estilo = estiloPorCategoria[widget.recursos.clasificador.clases[p.nivel]]!;
    final abierta = _paradasAbiertas.contains(p.clave);
    final completas = _paradasCompletas.contains(p.clave);
    final quieto = MediaQuery.of(context).disableAnimations;
    final km = p.kmDesdeAnterior == null
        ? ''
        : ' · ${kmLegible(p.kmDesdeAnterior!)} km ${i == 0 ? 'desde la partida' : 'desde la anterior'}';
    final mostradas = completas ? p.visitas : p.visitas.take(_primeras).toList();
    return KeyedSubtree(
      key: _anclasParada.putIfAbsent(p.clave, GlobalKey.new),
      child: _Caja(
        claveTest: 'parada-${i + 1}',
        seleccionada: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Semantics(
              button: true,
              expanded: abierta,
              child: InkWell(
                key: Key('parada-abrir-${i + 1}'),
                onTap: () => _alternarParada(p),
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
                  child: Row(
                    children: [
                      _Numero('${i + 1}', lleno: abierta),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _Titulos(
                          siguiente: i == 0,
                          titulo: p.lugar,
                          linea: Text('${p.municipio} · ${_plural(p.visitas.length, 'gestante', 'gestantes')}$km'),
                        ),
                      ),
                      const SizedBox(width: 8),
                      EtiquetaNivel(estilo),
                      const SizedBox(width: 8),
                      Container(
                        width: 28,
                        height: 28,
                        decoration: BoxDecoration(color: ColoresMaterna.campo, shape: BoxShape.circle),
                        child: AnimatedRotation(
                          turns: abierta ? .5 : 0,
                          duration: quieto ? Duration.zero : const Duration(milliseconds: 320),
                          curve: Curves.easeOutBack,
                          child: Icon(Icons.expand_more_rounded, size: 20, color: ColoresMaterna.ciruela900),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            _desplegable(
              context,
              abierta,
              Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  for (final v in mostradas)
                    _FilaGestante(
                      key: Key('visita-${v.ubicacion.id}'),
                      visita: v,
                      estilo: estiloPorCategoria[widget.recursos.clasificador.clases[v.ubicacion.clase]]!,
                      abierta: _abierta == v.ubicacion.id,
                      alTocar: () => setState(() => _abierta = _abierta == v.ubicacion.id ? null : v.ubicacion.id),
                      alMarcar: _marcar,
                    ),
                  if (!completas && p.visitas.length > _primeras)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(14, 4, 14, 14),
                      child: TextButton(
                        key: Key('parada-ver-todas-${i + 1}'),
                        style: TextButton.styleFrom(
                          backgroundColor: ColoresMaterna.campo,
                          foregroundColor: ColoresMaterna.ciruela900,
                          minimumSize: const Size.fromHeight(44),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                        ),
                        onPressed: () => setState(() => _paradasCompletas.add(p.clave)),
                        child: Text('Ver las ${p.visitas.length} gestantes', style: const TextStyle(fontWeight: FontWeight.w700)),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// El mapa, fijo arriba de la lista, con un degradado abajo para que las tarjetas pasen por debajo con suavidad.
class _MapaFijo extends SliverPersistentHeaderDelegate {
  _MapaFijo({required this.alto, required this.mapa});

  final double alto;
  final Widget mapa;

  @override
  double get minExtent => alto;
  @override
  double get maxExtent => alto;

  @override
  Widget build(BuildContext context, double encogido, bool superpuesto) => DecoratedBox(
    decoration: BoxDecoration(
      gradient: LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        stops: const [0, .9, 1],
        colors: [ColoresMaterna.crema, ColoresMaterna.crema, ColoresMaterna.crema.withValues(alpha: 0)],
      ),
    ),
    child: Padding(padding: const EdgeInsets.fromLTRB(16, 8, 16, 10), child: mapa),
  );

  @override
  bool shouldRebuild(_MapaFijo viejo) => viejo.mapa != mapa || viejo.alto != alto;
}

// ------------------------------------------------------------------ piezas de la pantalla

/// Aviso de la zona elegida en el mapa, con «Ver todas» para quitar el filtro.
class _AvisoZona extends StatelessWidget {
  const _AvisoZona({super.key, required this.nombre, required this.gestantes, required this.alQuitar});

  final String nombre;
  final int gestantes;
  final VoidCallback alQuitar;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.fromLTRB(12, 8, 6, 8),
    decoration: BoxDecoration(color: ColoresMaterna.ciruela100, borderRadius: BorderRadius.circular(14)),
    child: Row(
      key: const Key('zona-elegida'),
      children: [
        IconoDeTrazo(IconoTrazo.mapa, color: ColoresMaterna.ciruela900, tamano: 22),
        const SizedBox(width: 10),
        Expanded(
          child: Text.rich(
            TextSpan(
              children: [
                TextSpan(
                  text: '$nombre\n',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                TextSpan(text: '${_plural(gestantes, 'gestante', 'gestantes')} en esta zona del mapa'),
              ],
            ),
            style: TextStyle(color: ColoresMaterna.tinta, fontSize: 13, height: 1.35),
          ),
        ),
        TextButton.icon(
          key: const Key('zona-quitar'),
          onPressed: alQuitar,
          icon: const Icon(Icons.close_rounded, size: 18),
          label: const Text('Ver todas'),
        ),
      ],
    ),
  );
}

class _ChipEstado extends StatelessWidget {
  const _ChipEstado({super.key, required this.texto, required this.cuenta, required this.activo, required this.alTocar});

  final String texto;
  final int cuenta;
  final bool activo;
  final VoidCallback alTocar;

  @override
  Widget build(BuildContext context) {
    final marca = ColoresMaterna.ciruela900;
    return Semantics(
      button: true,
      selected: activo,
      child: Material(
        color: activo ? ColoresMaterna.vino : ColoresMaterna.tarjeta,
        shape: StadiumBorder(side: BorderSide(color: activo ? ColoresMaterna.vino : ColoresMaterna.borde, width: 1.5)),
        child: InkWell(
          customBorder: const StadiumBorder(),
          onTap: alTocar,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 6, 6, 6),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  texto,
                  style: TextStyle(
                    fontSize: 13.5,
                    fontWeight: activo ? FontWeight.w700 : FontWeight.w500,
                    color: activo ? Colors.white : ColoresMaterna.tintaSuave,
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  constraints: const BoxConstraints(minWidth: 26),
                  height: 26,
                  padding: const EdgeInsets.symmetric(horizontal: 6),
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: activo ? Colors.white.withValues(alpha: .22) : ColoresMaterna.campo,
                    borderRadius: BorderRadius.circular(13),
                  ),
                  child: Text(
                    '$cuenta',
                    style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: activo ? Colors.white : marca),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Avance extends StatelessWidget {
  const _Avance({required this.hechas, required this.total});

  final int hechas;
  final int total;

  @override
  Widget build(BuildContext context) => Row(
    key: const Key('visitas-avance'),
    children: [
      Text(
        'Visitadas: $hechas de $total',
        style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w500, color: ColoresMaterna.tintaSuave),
      ),
      const SizedBox(width: 10),
      Expanded(
        child: ClipRRect(
          borderRadius: BorderRadius.circular(3),
          child: LinearProgressIndicator(
            value: total == 0 ? 0 : hechas / total,
            minHeight: 6,
            backgroundColor: ColoresMaterna.fondoProgreso,
            color: estiloPorCategoria['Bajo Riesgo']!.barra,
          ),
        ),
      ),
    ],
  );
}

class _SelectorOrden extends StatelessWidget {
  const _SelectorOrden({required this.recorrido, required this.alCambiar});

  final bool recorrido;
  final ValueChanged<bool> alCambiar;

  Widget _opcion(String clave, String texto, Widget icono, bool activo, VoidCallback alTocar) => Expanded(
    child: Semantics(
      button: true,
      selected: activo,
      child: Material(
        color: activo ? ColoresMaterna.ciruela100 : Colors.transparent,
        borderRadius: BorderRadius.circular(12),
        child: InkWell(
          key: Key(clave),
          borderRadius: BorderRadius.circular(12),
          onTap: alTocar,
          child: SizedBox(
            height: 42,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                icono,
                const SizedBox(width: 6),
                Text(
                  texto,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: activo ? FontWeight.w700 : FontWeight.w500,
                    color: activo ? ColoresMaterna.ciruela900 : ColoresMaterna.tintaSuave,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  );

  @override
  Widget build(BuildContext context) {
    Color color(bool activo) => activo ? ColoresMaterna.ciruela900 : ColoresMaterna.tintaSuave;
    return Container(
      key: const Key('orden-visitas'),
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: ColoresMaterna.tarjeta,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [BoxShadow(color: ColoresMaterna.sombra, blurRadius: 14, offset: const Offset(0, 4))],
      ),
      child: Row(
        children: [
          _opcion(
            'orden-prioridad',
            'Por prioridad',
            Icon(Icons.priority_high_rounded, size: 18, color: color(!recorrido)),
            !recorrido,
            () => alCambiar(false),
          ),
          _opcion(
            'orden-recorrido',
            'Recorrido',
            Icon(Icons.route_rounded, size: 18, color: color(recorrido)),
            recorrido,
            () => alCambiar(true),
          ),
        ],
      ),
    );
  }
}

class _Seccion extends StatelessWidget {
  const _Seccion(this.texto, this.cuenta);

  final String texto;
  final int cuenta;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(4, 10, 4, 8),
    child: Row(
      children: [
        Text(
          texto.toUpperCase(),
          style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, letterSpacing: .6, color: ColoresMaterna.ciruela900),
        ),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 1),
          decoration: BoxDecoration(color: ColoresMaterna.ciruela100, borderRadius: BorderRadius.circular(10)),
          child: Text(
            '$cuenta',
            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: ColoresMaterna.ciruela900),
          ),
        ),
      ],
    ),
  );
}

class _Vacio extends StatelessWidget {
  const _Vacio({required this.titulo, required this.texto});

  final String titulo;
  final String texto;

  @override
  Widget build(BuildContext context) {
    final ok = estiloPorCategoria['Bajo Riesgo']!;
    return Container(
      key: const Key('visitas-lista-vacia'),
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 26),
      decoration: BoxDecoration(color: ColoresMaterna.tarjeta.withValues(alpha: .7), borderRadius: BorderRadius.circular(20)),
      child: Column(
        children: [
          CircleAvatar(
            radius: 26,
            backgroundColor: ok.fondo,
            child: Icon(Icons.check_rounded, color: ok.tinta, size: 28),
          ),
          const SizedBox(height: 10),
          Text(
            titulo,
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: ColoresMaterna.tinta),
          ),
          const SizedBox(height: 4),
          Text(
            texto,
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 13, color: ColoresMaterna.tintaSuave),
          ),
        ],
      ),
    );
  }
}

/// Tarjeta blanca redondeada de la lista (gestante o parada).
class _Caja extends StatelessWidget {
  const _Caja({required this.child, required this.seleccionada, this.claveTest, this.atenuada = false});

  final Widget child;
  final bool seleccionada;
  final String? claveTest;
  final bool atenuada;

  @override
  Widget build(BuildContext context) => Padding(
    key: claveTest == null ? null : Key(claveTest!),
    padding: const EdgeInsets.only(bottom: 9),
    // seleccionada: se acerca un poco (escala 1,03) con una curva suave, sin borde
    child: AnimatedScale(
      key: seleccionada ? const Key('tarjeta-seleccionada') : null,
      scale: seleccionada ? 1.03 : 1,
      duration: MediaQuery.of(context).disableAnimations ? Duration.zero : const Duration(milliseconds: 230),
      curve: Curves.easeOutCubic,
      child: Container(
        clipBehavior: Clip.antiAlias,
        decoration: BoxDecoration(
          color: atenuada ? ColoresMaterna.tarjeta.withValues(alpha: .72) : ColoresMaterna.tarjeta,
          borderRadius: BorderRadius.circular(20),
          boxShadow: [BoxShadow(color: ColoresMaterna.sombra, blurRadius: 18, offset: const Offset(0, 6))],
        ),
        child: Material(type: MaterialType.transparency, child: child),
      ),
    ),
  );
}

class _Numero extends StatelessWidget {
  const _Numero(this.texto, {this.hecha = false, this.lleno = false});

  final String texto;
  final bool hecha;

  /// Cabecera desplegada: el número en vino lleno (como el mockup), sin borde en la tarjeta.
  final bool lleno;

  @override
  Widget build(BuildContext context) {
    final ok = estiloPorCategoria['Bajo Riesgo']!;
    return AnimatedContainer(
      duration: MediaQuery.of(context).disableAnimations ? Duration.zero : const Duration(milliseconds: 250),
      width: 34,
      height: 34,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: hecha ? ok.fondo : (lleno ? ColoresMaterna.vino : ColoresMaterna.campo),
        borderRadius: BorderRadius.circular(12),
      ),
      child: hecha
          ? Icon(Icons.check_rounded, size: 18, color: ok.tinta)
          : Text(
              texto,
              style: TextStyle(
                fontWeight: FontWeight.w700,
                fontSize: 15,
                color: lleno ? Colors.white : ColoresMaterna.ciruela900,
              ),
            ),
    );
  }
}

class _Titulos extends StatelessWidget {
  const _Titulos({required this.titulo, required this.linea, this.siguiente = false, this.atenuado = false});

  final String titulo;
  final Widget linea;
  final bool siguiente;
  final bool atenuado;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      if (siguiente)
        Text(
          'SIGUIENTE',
          key: const Key('visita-siguiente'),
          style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700, letterSpacing: .4, color: ColoresMaterna.ciruela900),
        ),
      Text(
        titulo,
        style: TextStyle(
          fontSize: 15,
          fontWeight: FontWeight.w500,
          color: atenuado ? ColoresMaterna.tintaSuave : ColoresMaterna.tinta,
        ),
      ),
      DefaultTextStyle.merge(
        style: TextStyle(fontSize: 12.5, color: ColoresMaterna.tintaSuave, height: 1.3),
        child: linea,
      ),
    ],
  );
}

/// Línea de apoyo bajo el nombre: cuándo fue el último contacto, la visita o el intento fallido.
Widget _lineaEstado(RegistroUbicacion u, {String? antes}) {
  final prefijo = antes == null ? '' : '$antes · ';
  return switch (u.estado) {
    EstadoVisita.visitada => Text('${prefijo}Visitada ${haceCuanto(u.ultimoContacto)}'),
    EstadoVisita.sinLocalizar => Text.rich(
      TextSpan(
        children: [
          TextSpan(text: prefijo),
          TextSpan(
            text: 'No la encontraron',
            style: TextStyle(color: estiloPorCategoria['Alto Riesgo']!.tinta, fontWeight: FontWeight.w500),
          ),
          TextSpan(text: ' · sin contacto ${haceCuanto(u.ultimoContacto)}'),
        ],
      ),
      key: Key('sin-localizar-${u.id}'),
    ),
    EstadoVisita.pendiente => Text('${prefijo}Sin contacto ${haceCuanto(u.ultimoContacto)}'),
  };
}

/// Botón redondo ✓: marca la visita o, si ya está hecha, la devuelve a pendientes.
class _BotonVisita extends StatelessWidget {
  const _BotonVisita({required this.visita, required this.alMarcar, this.tamano = 38});

  final Visita visita;
  final Future<void> Function(Visita, EstadoVisita) alMarcar;
  final double tamano;

  @override
  Widget build(BuildContext context) {
    final u = visita.ubicacion;
    final hecha = u.estado == EstadoVisita.visitada;
    final ok = estiloPorCategoria['Bajo Riesgo']!.degradado.first;
    final borde = ColoresMaterna.oscuro ? const Color(0xFF4E3B47) : const Color(0xFFD9C3CF);
    return Tooltip(
      message: hecha ? 'Devolver a pendientes' : 'Marcar como visitada',
      child: Semantics(
        button: true,
        checked: hecha,
        label: hecha ? 'Devolver a pendientes' : 'Marcar como visitada',
        excludeSemantics: true,
        child: InkResponse(
          key: Key(hecha ? 'devolver-${u.id}' : 'visitada-${u.id}'),
          radius: tamano / 2 + 4,
          onTap: () => alMarcar(visita, hecha ? EstadoVisita.pendiente : EstadoVisita.visitada),
          child: Container(
            width: tamano,
            height: tamano,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: hecha ? ok : ColoresMaterna.tarjeta,
              border: Border.all(color: hecha ? ok : borde, width: 2),
            ),
            child: Icon(Icons.check_rounded, size: tamano * .5, color: hecha ? Colors.white : borde),
          ),
        ),
      ),
    );
  }
}

/// Lo que se ve al tocar una gestante: código, distancia a la cabecera, referencia y «No la encontramos».
class _Detalle extends StatelessWidget {
  const _Detalle({required this.visita, required this.alMarcar, required this.sangria, this.conCodigo = true});

  final Visita visita;
  final Future<void> Function(Visita, EstadoVisita) alMarcar;
  final double sangria;
  final bool conCodigo;

  @override
  Widget build(BuildContext context) {
    final u = visita.ubicacion;
    final lineas = [
      if (conCodigo) codigoGestante(u.idSeudonimo),
      if (visita.kmCabecera != null)
        'A ${kmLegible(visita.kmCabecera!)} km de la cabecera de ${visita.cabecera!.replaceFirst('Cabecera de ', '')} (aprox.)',
      if (u.referenciaRol != null) 'Referencia: ${u.referenciaRol}${u.referenciaApodo == null ? '' : ' · ${u.referenciaApodo}'}',
    ];
    return Padding(
      key: Key('detalle-visita-${u.id}'),
      padding: EdgeInsets.fromLTRB(sangria, 0, 14, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(lineas.join('\n'), style: TextStyle(fontSize: 12.5, height: 1.5, color: ColoresMaterna.tintaSuave)),
          if (u.estado == EstadoVisita.pendiente)
            TextButton(
              key: Key('no-encontrada-${u.id}'),
              style: TextButton.styleFrom(padding: EdgeInsets.zero, minimumSize: const Size(0, 40)),
              onPressed: () => alMarcar(visita, EstadoVisita.sinLocalizar),
              child: const Text('No la encontramos'),
            ),
        ],
      ),
    );
  }
}

Widget _desplegable(BuildContext context, bool abierta, Widget hijo) => AnimatedSize(
  duration: MediaQuery.of(context).disableAnimations ? Duration.zero : const Duration(milliseconds: 260),
  curve: Curves.easeOutCubic,
  alignment: Alignment.topCenter,
  child: abierta ? hijo : const SizedBox(width: double.infinity),
);

/// Una gestante en «Por prioridad» o en «Visitadas»: número, lugar, una línea de apoyo, nivel y ✓.
class _TarjetaVisita extends StatelessWidget {
  const _TarjetaVisita({
    super.key,
    required this.visita,
    required this.numero,
    required this.siguiente,
    required this.estilo,
    required this.seleccionada,
    required this.abierta,
    required this.alTocar,
    required this.alMarcar,
  });

  final Visita visita;
  final int? numero;
  final bool siguiente;
  final EstiloRiesgo estilo;
  final bool seleccionada;
  final bool abierta;
  final VoidCallback alTocar;
  final Future<void> Function(Visita, EstadoVisita) alMarcar;

  @override
  Widget build(BuildContext context) {
    final u = visita.ubicacion;
    final hecha = u.estado == EstadoVisita.visitada;
    return _Caja(
      seleccionada: seleccionada,
      atenuada: hecha,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          InkWell(
            onTap: alTocar,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
              child: Row(
                children: [
                  _Numero('${numero ?? ''}', hecha: hecha),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _Titulos(
                      siguiente: siguiente,
                      atenuado: hecha,
                      titulo: visita.lugar,
                      linea: _lineaEstado(u, antes: visita.municipio),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Opacity(opacity: hecha ? .65 : 1, child: EtiquetaNivel(estilo)),
                  const SizedBox(width: 8),
                  _BotonVisita(visita: visita, alMarcar: alMarcar),
                ],
              ),
            ),
          ),
          _desplegable(context, abierta, _Detalle(visita: visita, alMarcar: alMarcar, sangria: 60)),
        ],
      ),
    );
  }
}

/// Una gestante dentro de una parada del recorrido.
class _FilaGestante extends StatelessWidget {
  const _FilaGestante({
    super.key,
    required this.visita,
    required this.estilo,
    required this.abierta,
    required this.alTocar,
    required this.alMarcar,
  });

  final Visita visita;
  final EstiloRiesgo estilo;
  final bool abierta;
  final VoidCallback alTocar;
  final Future<void> Function(Visita, EstadoVisita) alMarcar;

  @override
  Widget build(BuildContext context) {
    final u = visita.ubicacion;
    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border(top: BorderSide(color: ColoresMaterna.borde)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          InkWell(
            onTap: alTocar,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(60, 9, 12, 9),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          codigoGestante(u.idSeudonimo),
                          style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w500, color: ColoresMaterna.tinta),
                        ),
                        DefaultTextStyle.merge(
                          style: TextStyle(fontSize: 12.5, color: ColoresMaterna.tintaSuave),
                          child: _lineaEstado(u),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  EtiquetaNivel(estilo),
                  const SizedBox(width: 8),
                  _BotonVisita(visita: visita, alMarcar: alMarcar, tamano: 34),
                ],
              ),
            ),
          ),
          _desplegable(context, abierta, _Detalle(visita: visita, alMarcar: alMarcar, sangria: 60, conCodigo: false)),
        ],
      ),
    );
  }
}
