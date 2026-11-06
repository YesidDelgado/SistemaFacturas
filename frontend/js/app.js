"use strict";

// Controla la navegación, formularios, catálogo, OCR, IA y facturas del frontend.

// Rutas de los servicios consumidos por la interfaz.
const API_FACTURAS = "/facturas";
const API_USUARIOS = "/usuarios";
const API_IA = "/ia";
const API_OCR = "/ocr";
const API_CATALOGO = "/catalogo";
const API_FINANZAS = "/finanzas";

// Estado temporal de sesión, facturas, catálogo y edición.
let sesion = null;
let facturasAdmin = [];
let productosCatalogo = [];
let usuariosAdmin = [];
let idEditando = null;
let ultimaFacturaRegistrada = null;

// Busca un elemento del documento por su identificador.
const $ = (id) => document.getElementById(id);
// Vistas principales que se alternan durante la navegación.
const vistas = ["vista-ingreso", "vista-login-cliente", "vista-login-admin", "vista-cliente", "vista-admin"];

// Muestra únicamente la vista solicitada y vuelve al inicio de la página.
function mostrarVista(id) {
    vistas.forEach((vista) => $(vista).classList.toggle("oculta", vista !== id));
    window.scrollTo({ top: 0, behavior: "smooth" });
}

// Presenta un mensaje de estado en un elemento de la interfaz.
function mostrarMensaje(id, texto, tipo = "") {
    const elemento = $(id);
    elemento.textContent = texto || "";
    elemento.className = `message ${tipo}`.trim();
}

// Ejecuta solicitudes HTTP y normaliza sus respuestas y errores.
async function solicitar(url, opciones = {}) {
    const formData = opciones.body instanceof FormData;
    const respuesta = await fetch(url, {
        credentials: "same-origin",
        ...opciones,
        headers: {
            ...(opciones.body && !formData ? { "Content-Type": "application/json" } : {}),
            ...(opciones.headers || {})
        }
    });
    const texto = await respuesta.text();
    let datos = {};
    if (texto) {
        try { datos = JSON.parse(texto); } catch { datos = { detail: texto }; }
    }
    if (!respuesta.ok) {
        const detalle = datos.detail || datos.mensaje || "Ocurrió un error.";
        throw new Error(typeof detalle === "string" ? detalle : JSON.stringify(detalle));
    }
    return datos;
}

// Convierte un error técnico en un mensaje comprensible para el usuario.
function mensajeError(error) {
    return error instanceof TypeError
        ? "No se pudo conectar con el servidor."
        : error.message || "Ocurrió un error inesperado.";
}

// Formatea un valor numérico como moneda colombiana.
function formatoPesos(valor) {
    return new Intl.NumberFormat("es-CO", {
        style: "currency", currency: "COP", maximumFractionDigits: 2
    }).format(Number(valor) || 0);
}

// Devuelve la fecha local actual con formato compatible con el formulario.
function fechaHoy() {
    const fecha = new Date();
    return new Date(fecha.getTime() - fecha.getTimezoneOffset() * 60000)
        .toISOString().slice(0, 10);
}

// Escapa texto antes de insertarlo dentro de HTML.
function escaparHTML(valor) {
    return String(valor ?? "").replace(/[&<>"']/g, (caracter) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[caracter]);
}

// Devuelve el contenedor de detalles según el tipo de usuario.
function nombreCampo(scope) {
    return scope === "admin" ? "detalles-admin" : "detalles-cliente";
}

// Devuelve el campo de total según el tipo de usuario.
function totalCampo(scope) {
    return scope === "admin" ? "valor-admin" : "valor-cliente";
}

// Devuelve el contenedor de totales según el tipo de usuario.
function totalesCampo(scope) {
    return scope === "admin" ? "totales-admin" : "totales-cliente";
}

// Construye una fila editable para un producto de la factura.
// Construcción y cálculo de líneas de productos.
function crearFilaDetalle(scope, detalle = {}) {
    const fila = document.createElement("div");
    fila.className = "detail-row";
    fila.innerHTML = `
        <input data-field="codigo" placeholder="Código">
        <input data-field="nombre" placeholder="Producto">
        <input data-field="cantidad" type="number" min="0.01" step="0.01" value="1" placeholder="Cant.">
        <input data-field="precio" type="number" min="0" step="0.01" placeholder="Precio">
        <input data-field="iva" type="number" min="0" max="100" step="0.01" placeholder="IVA %">
        <input data-field="subtotal" readonly placeholder="Subtotal">
        <button type="button" class="remove-detail" aria-label="Quitar producto">×</button>`;
    fila.querySelector('[data-field="codigo"]').value = detalle.codigo || "";
    fila.querySelector('[data-field="nombre"]').value = detalle.nombre || "";
    fila.querySelector('[data-field="cantidad"]').value = detalle.cantidad ?? 1;
    fila.querySelector('[data-field="precio"]').value = detalle.valor_unitario ?? "";
    fila.querySelector('[data-field="iva"]').value = detalle.iva_porcentaje ?? 0;
    fila.querySelector('[data-field="subtotal"]').value =
        detalle.subtotal == null ? "" : Number(detalle.subtotal).toFixed(2);
    fila.querySelector('[data-field="codigo"]').addEventListener("change", () => completarProducto(fila, scope));
    fila.querySelector('[data-field="codigo"]').addEventListener("keydown", (evento) => {
        if (evento.key === "Enter") {
            evento.preventDefault();
            completarProducto(fila, scope);
        }
    });
    fila.querySelectorAll("input").forEach((input) => {
        if (input.dataset.field !== "codigo") input.addEventListener("input", () => calcularDetalles(scope));
    });
    fila.querySelector(".remove-detail").addEventListener("click", () => {
        const contenedor = $(nombreCampo(scope));
        if (contenedor.children.length > 1) fila.remove();
        calcularDetalles(scope);
    });
    return fila;
}

// Agrega una nueva fila de producto y recalcula los totales.
function agregarFilaDetalle(scope, detalle = {}) {
    $(nombreCampo(scope)).appendChild(crearFilaDetalle(scope, detalle));
    calcularDetalles(scope);
}

// Completa un producto del catálogo y consolida códigos repetidos.
function completarProducto(fila, scope) {
    const codigo = fila.querySelector('[data-field="codigo"]').value.trim().toLowerCase();
    const producto = productosCatalogo.find((item) => String(item.codigo).toLowerCase() === codigo);
    completarFilaConProducto(fila, scope, producto);
}

// Asigna los datos del catálogo y consolida productos repetidos en la factura.
function completarFilaConProducto(fila, scope, producto) {
    const nombre = fila.querySelector('[data-field="nombre"]');
    const precio = fila.querySelector('[data-field="precio"]');
    const iva = fila.querySelector('[data-field="iva"]');
    if (producto) {
        const filaExistente = [...document.querySelectorAll(`#${nombreCampo(scope)} .detail-row`)]
            .find((otraFila) =>
                otraFila !== fila &&
                Number(otraFila.dataset.productoId) === Number(producto.id)
            );
        if (filaExistente) {
            const cantidadExistente = filaExistente.querySelector('[data-field="cantidad"]');
            cantidadExistente.value = (Number(cantidadExistente.value) || 0) + 1;
            fila.remove();
            calcularDetalles(scope);
            return;
        }
        fila.dataset.productoId = producto.id;
        nombre.value = producto.nombre;
        precio.value = producto.precio;
        iva.value = producto.iva_porcentaje;
        nombre.readOnly = true;
        precio.readOnly = true;
        iva.readOnly = true;
    } else {
        delete fila.dataset.productoId;
        nombre.readOnly = false;
        precio.readOnly = false;
        iva.readOnly = false;
    }
    calcularDetalles(scope);
}

// Inserta un producto del catálogo en la primera fila disponible de la factura.
function agregarProductoDesdeCatalogo(codigo, scope = "admin") {
    const producto = productosCatalogo.find(
        (item) => String(item.codigo).toLowerCase() === String(codigo).toLowerCase()
    );
    if (!producto) return;
    const filas = [...document.querySelectorAll(`#${nombreCampo(scope)} .detail-row`)];
    const filaVacia = filas.find((fila) => !fila.querySelector('[data-field="nombre"]').value.trim());
    const fila = filaVacia || crearFilaDetalle(scope);
    if (!filaVacia) $(nombreCampo(scope)).appendChild(fila);
    fila.querySelector('[data-field="codigo"]').value = producto.codigo;
    completarProducto(fila, scope);
}

// Calcula subtotales, IVA y total de las filas de productos.
function calcularDetalles(scope) {
    let subtotal = 0;
    let impuestos = 0;
    let tieneProducto = false;
    document.querySelectorAll(`#${nombreCampo(scope)} .detail-row`).forEach((fila) => {
        const cantidad = Number(fila.querySelector('[data-field="cantidad"]').value) || 0;
        const precio = Number(fila.querySelector('[data-field="precio"]').value) || 0;
        const iva = Number(fila.querySelector('[data-field="iva"]').value) || 0;
        const linea = Math.max(0, cantidad * precio);
        const impuesto = linea * iva / 100;
        subtotal += linea;
        impuestos += impuesto;
        tieneProducto = tieneProducto || Boolean(fila.querySelector('[data-field="nombre"]').value.trim() && cantidad > 0);
        fila.querySelector('[data-field="subtotal"]').value = linea ? linea.toFixed(2) : "";
    });
    const total = subtotal + impuestos;
    const campoTotal = $(totalCampo(scope));
    campoTotal.readOnly = tieneProducto;
    if (tieneProducto) campoTotal.value = total.toFixed(2);
    $(totalesCampo(scope)).innerHTML =
        `<span>Subtotal: <strong>${formatoPesos(subtotal)}</strong></span>` +
        `<span>IVA: <strong>${formatoPesos(impuestos)}</strong></span>` +
        `<span>Total: <strong>${formatoPesos(total)}</strong></span>`;
}

// Lee y valida los detalles diligenciados en el formulario.
function leerDetalles(scope) {
    return [...document.querySelectorAll(`#${nombreCampo(scope)} .detail-row`)]
        .map((fila) => ({
            producto_id: fila.dataset.productoId ? Number(fila.dataset.productoId) : null,
            nombre: fila.querySelector('[data-field="nombre"]').value.trim(),
            cantidad: Number(fila.querySelector('[data-field="cantidad"]').value),
            valor_unitario: Number(fila.querySelector('[data-field="precio"]').value),
            iva_porcentaje: Number(fila.querySelector('[data-field="iva"]').value) || 0,
            descuento: 0
        }))
        .filter((detalle) => detalle.nombre && detalle.cantidad > 0 && detalle.valor_unitario >= 0);
}

// Restablece las filas de productos de un formulario.
function limpiarDetalles(scope) {
    $(nombreCampo(scope)).innerHTML = "";
    agregarFilaDetalle(scope);
}

// Carga productos detectados por OCR o IA en el formulario.
function cargarDetalles(scope, detalles) {
    $(nombreCampo(scope)).innerHTML = "";
    const consolidados = new Map();
    detalles.forEach((detalle) => {
        const clave = detalle.producto_id
            ? `id:${detalle.producto_id}`
            : `${String(detalle.nombre || "").trim().toLowerCase()}|${detalle.valor_unitario || 0}|${detalle.iva_porcentaje || 0}`;
        const anterior = consolidados.get(clave);
        if (anterior) {
            anterior.cantidad = (Number(anterior.cantidad) || 1) + (Number(detalle.cantidad) || 1);
        } else {
            consolidados.set(clave, { ...detalle, cantidad: detalle.cantidad ?? 1 });
        }
    });
    if (!consolidados.size) agregarFilaDetalle(scope);
    consolidados.forEach((detalle) => agregarFilaDetalle(scope, detalle));
    calcularDetalles(scope);
}

// Obtiene y muestra el catálogo disponible para la sesión actual.
// Carga de catálogo y resultados de extracción.
async function cargarCatalogo() {
    if (!sesion) return;
    try {
        productosCatalogo = await solicitar(`${API_CATALOGO}/productos`);
        if ($("lista-productos")) {
            $("lista-productos").innerHTML = productosCatalogo.length
                ? productosCatalogo.map((producto) =>
                        `<div class="product-chip"><input type="checkbox" class="producto-seleccionado" value="${escaparHTML(producto.codigo)}"><span>${escaparHTML(producto.codigo)} · ${escaparHTML(producto.nombre)} · Venta ${formatoPesos(producto.precio)} · Costo ${formatoPesos(producto.costo_adquisicion)} + ${producto.iva_porcentaje}% IVA</span><button type="button" class="button button-secondary button-small agregar-producto-factura" data-codigo="${escaparHTML(producto.codigo)}">Agregar a factura</button><button type="button" class="button button-secondary button-small editar-producto" data-codigo="${escaparHTML(producto.codigo)}">Editar</button></div>`
                ).join("")
                : "<small>No hay productos cargados.</small>";
        }

    } catch (error) {
        if ($("lista-productos")) $("lista-productos").textContent = mensajeError(error);
    }
}

// Carga los indicadores y el comportamiento comercial del periodo elegido.
async function cargarFinanzas() {
    try {
        if (!$("finanzas-desde").value || !$("finanzas-hasta").value) {
            $("indicadores-finanzas").innerHTML = "";
            $("grafica-productos").innerHTML = "";
            $("grafica-periodos").innerHTML = "";
            $("tabla-finanzas").innerHTML = "";
            mostrarMensaje("mensaje-finanzas", "Selecciona un rango de fechas y pulsa Actualizar.", "error");
            return;
        }
        const parametros = new URLSearchParams();
        if ($("finanzas-desde").value) parametros.set("desde", $("finanzas-desde").value);
        if ($("finanzas-hasta").value) parametros.set("hasta", $("finanzas-hasta").value);
        const datos = await solicitar(`${API_FINANZAS}/analisis?${parametros}`);
        const resumen = datos.resumen;
        $("indicadores-finanzas").innerHTML = [
            ["Facturas", resumen.facturas], ["Ventas", formatoPesos(resumen.ventas)],
            ["IVA", formatoPesos(resumen.iva)], ["Costos", formatoPesos(resumen.costos)],
            ["Utilidad", formatoPesos(resumen.utilidad)], ["Pérdida", formatoPesos(resumen.perdida)]
        ].map(([nombre, valor]) => `<div class="finance-indicator"><span>${nombre}</span><strong>${valor}</strong></div>`).join("");
        $("tabla-finanzas").innerHTML = `<table><thead><tr><th>Producto</th><th>Unidades</th><th>Ventas</th><th>Costos</th><th>Utilidad</th></tr></thead><tbody>${
            datos.productos.length ? datos.productos.map((producto) => `<tr><td>${escaparHTML(producto.nombre)}</td><td>${producto.unidades}</td><td>${formatoPesos(producto.ventas)}</td><td>${formatoPesos(producto.costos)}</td><td>${formatoPesos(producto.utilidad)}</td></tr>`).join("") : "<tr><td colspan='5'>No hay ventas en el periodo.</td></tr>"
        }</tbody></table>`;
        const maxProducto = Math.max(...datos.productos.map((producto) => Number(producto.ventas) || 0), 1);
        $("grafica-productos").innerHTML = datos.productos.length
            ? datos.productos.slice(0, 10).map((producto) => `
                <div class="finance-bar-row"><span>${escaparHTML(producto.nombre)}</span>
                    <div class="finance-bar-track"><i style="width:${Math.max(3, (Number(producto.ventas) / maxProducto) * 100)}%"></i></div>
                    <b>${formatoPesos(producto.utilidad)}</b>
                </div>`).join("")
            : "<small>No hay productos en el periodo.</small>";
        const maxPeriodo = Math.max(...datos.mensual.map((periodo) => Number(periodo.ventas) || 0), 1);
        $("grafica-periodos").innerHTML = datos.mensual.length
            ? datos.mensual.map((periodo) => `
                <div class="finance-bar-row"><span>${escaparHTML(periodo.periodo)}</span>
                    <div class="finance-bar-track"><i class="period-bar" style="width:${Math.max(3, (Number(periodo.ventas) / maxPeriodo) * 100)}%"></i></div>
                    <b>${formatoPesos(periodo.ventas)}</b>
                </div>`).join("")
            : "<small>No hay periodos en el rango.</small>";
        mostrarMensaje("mensaje-finanzas", "Análisis actualizado.", "exito");
    } catch (error) { mostrarMensaje("mensaje-finanzas", mensajeError(error), "error"); }
}

// Abre una descarga protegida por la sesión administrativa actual.
function descargarInformeFinanciero(extension) {
    if (!$("finanzas-desde").value || !$("finanzas-hasta").value) {
        mostrarMensaje("mensaje-finanzas", "Selecciona Desde y Hasta antes de descargar.", "error");
        return;
    }
    const parametros = new URLSearchParams();
    if ($("finanzas-desde").value) parametros.set("desde", $("finanzas-desde").value);
    if ($("finanzas-hasta").value) parametros.set("hasta", $("finanzas-hasta").value);
    window.open(`${API_FINANZAS}/reporte.${extension}?${parametros}`, "_blank", "noopener");
}

// Solicita y ejecuta el borrado controlado de productos del catálogo.
async function borrarCatalogo(modo, codigos, confirmacion) {
    try {
        const respuesta = await solicitar(`${API_CATALOGO}/borrar`, {
            method: "POST", body: JSON.stringify({ modo, codigos, confirmacion })
        });
        mostrarMensaje("mensaje-catalogo", `${respuesta.mensaje} Eliminados: ${respuesta.eliminados}. Protegidos: ${respuesta.protegidos}.`, "exito");
        await cargarCatalogo();
    } catch (error) { mostrarMensaje("mensaje-catalogo", mensajeError(error), "error"); }
}

// Consulta el consecutivo de factura y lo coloca en el formulario.
async function cargarProximoCodigo(id) {
    try {
        const datos = await solicitar(`${API_FACTURAS}/proximo-codigo`);
        $(id).value = datos.factura || "";
    } catch (error) {
        console.error("No se pudo obtener el consecutivo:", error);
    }
}

// Muestra la respuesta completa de OCR o IA en formato JSON.
function mostrarResultado(id, datos) {
    $(id).textContent = JSON.stringify(datos, null, 2);
    $(id).classList.remove("oculta");
}

// Presenta los campos y productos estructurados en una tabla.
function mostrarFacturaEstructurada(scope, datos) {
    const campos = datos.datos_estructurados || datos;
    const productos = Array.isArray(campos.productos) ? campos.productos : [];
    const filas = productos.map((producto) => `
        <tr><td>${escaparHTML(producto.nombre || "Sin nombre")}</td>
        <td>${producto.cantidad ?? "No detectada"}</td>
        <td>${producto.valor_unitario == null ? "No detectado" : formatoPesos(producto.valor_unitario)}</td>
        <td>${producto.iva_porcentaje == null ? "No detectado" : `${producto.iva_porcentaje}%`}</td>
        <td>${producto.subtotal == null ? "No calculado" : formatoPesos(producto.subtotal)}</td></tr>
    `).join("");
    const validacion = campos.validacion || {};
    const advertencias = Array.isArray(datos.advertencias)
        ? datos.advertencias
        : [];
    const elemento = $(`datos-estructurados-${scope}`);
    elemento.innerHTML = `
        <div class="structured-grid">
            <span><b>Proveedor:</b> ${escaparHTML(campos.razon_social || "No detectado")}</span>
            <span><b>NIT:</b> ${escaparHTML(campos.nit_proveedor || "No detectado")}</span>
            <span><b>Factura:</b> ${escaparHTML(campos.numero_factura || "No detectado")}</span>
            <span><b>Fecha:</b> ${escaparHTML(campos.fecha || "No detectada")}</span>
            <span><b>Subtotal:</b> ${campos.subtotal_general == null ? "No calculado" : formatoPesos(campos.subtotal_general)}</span>
            <span><b>IVA:</b> ${campos.iva == null ? "No calculado" : formatoPesos(campos.iva)}</span>
            <span><b>Total:</b> ${campos.total == null ? "No detectado" : formatoPesos(campos.total)}</span>
            <span><b>Validación:</b> ${validacion.coincide ? "Coincide" : "Requiere revisión"}</span>
        </div>
        ${advertencias.length ? `<p class="message">${advertencias.map((advertencia) => escaparHTML(advertencia)).join(" ")}</p>` : ""}
        ${filas ? `<div class="table-wrap"><table><thead><tr><th>Producto</th><th>Cantidad</th><th>Unitario</th><th>IVA</th><th>Subtotal</th></tr></thead><tbody>${filas}</tbody></table></div>` : "<p>No se detectaron productos con suficiente confianza.</p>"}`;
    elemento.classList.remove("oculta");
}

// Aplica los datos estructurados detectados al formulario de factura.
function aplicarDatosEstructurados(scope, datos) {
    const campos = datos.datos_estructurados || datos;
    const cliente = scope === "admin" ? "nombre-factura-admin" : "nombre-factura-cliente";
    const fecha = scope === "admin" ? "fecha-admin" : "fecha-cliente";
    const proveedor = scope === "admin" ? "proveedor-factura-admin" : "proveedor-factura-cliente";
    const nit = scope === "admin" ? "nit-factura-admin" : "nit-factura-cliente";
    if (campos.cliente) $(cliente).value = campos.cliente;
    if (campos.fecha) $(fecha).value = campos.fecha;
    if (campos.razon_social) $(proveedor).value = campos.razon_social;
    if (campos.nit_proveedor) $(nit).value = campos.nit_proveedor;
    if (campos.productos?.length) cargarDetalles(scope, campos.productos);
    if (campos.total != null) $(totalCampo(scope)).value = campos.total;
    calcularDetalles(scope);
}

// Envía un documento a Gemini y carga el resultado estructurado.
// Procesamiento de documentos con IA y OCR local.
async function analizarIA(scope) {
    const archivo = $(`archivo-ocr-${scope}`).files[0];
    if (!archivo) {
        mostrarMensaje(`mensaje-ocr-${scope}`, "Selecciona un documento.", "error");
        return;
    }
    const formulario = new FormData();
    formulario.append("archivo", archivo);
    const boton = $(`btn-ocr-${scope}`);
    boton.disabled = true;
    mostrarMensaje(`mensaje-ocr-${scope}`, "Analizando documento...");
    try {
        const respuesta = await solicitar(`${API_IA}/analizar-factura`, { method: "POST", body: formulario });
        const datos = respuesta.datos || {};
        aplicarDatosEstructurados(scope, datos);
        mostrarFacturaEstructurada(scope, datos);
        mostrarResultado(`resultado-ocr-${scope}`, datos);
        mostrarMensaje(`mensaje-ocr-${scope}`, "Datos extraídos. Revisa antes de guardar.", "exito");
    } catch (error) {
        mostrarMensaje(`mensaje-ocr-${scope}`, mensajeError(error), "error");
    } finally {
        boton.disabled = false;
    }
}

// Envía un documento al OCR local y carga el resultado detectado.
async function analizarOCRLocal(scope) {
    const archivo = $(`archivo-ocr-${scope}`).files[0];
    if (!archivo) {
        mostrarMensaje(`mensaje-ocr-${scope}`, "Selecciona un documento.", "error");
        return;
    }
    const formulario = new FormData();
    formulario.append("archivo", archivo);
    const boton = $(`btn-ocr-local-${scope}`);
    boton.disabled = true;
    try {
        const respuesta = await solicitar(`${API_OCR}/extraer`, { method: "POST", body: formulario });
        const datos = respuesta.datos || {};
        mostrarResultado(`resultado-ocr-${scope}`, datos);
        mostrarFacturaEstructurada(scope, datos.datos_estructurados || datos);
        aplicarDatosEstructurados(scope, datos);
        mostrarMensaje(`mensaje-ocr-${scope}`, "OCR completado. Revisa el texto.", "exito");
    } catch (error) {
        mostrarMensaje(`mensaje-ocr-${scope}`, mensajeError(error), "error");
    } finally {
        boton.disabled = false;
    }
}

// Recoge los datos generales y detalles del formulario de factura.
// Registro, edición e historial de facturas.
function datosFactura(scope) {
    return {
        cliente: $(`nombre-factura-${scope}`).value.trim(),
        proveedor: $(`proveedor-factura-${scope}`).value.trim() || null,
        nit_proveedor: $(`nit-factura-${scope}`).value.trim() || null,
        fecha: $(`fecha-${scope}`).value,
        total: Number($(totalCampo(scope)).value) || 0,
        detalles: leerDetalles(scope)
    };
}

// Guarda una factura nueva o actualiza la factura en edición.
async function registrarFactura(scope, evento) {
    evento.preventDefault();
    const boton = scope === "admin" ? $("btn-guardar-admin") : $("btn-registrar-cliente");
    boton.disabled = true;
    try {
        const url = scope === "admin" && idEditando !== null ? `${API_FACTURAS}/${idEditando}` : API_FACTURAS;
        const respuesta = await solicitar(url, {
            method: scope === "admin" && idEditando !== null ? "PUT" : "POST",
            body: JSON.stringify(datosFactura(scope))
        });
        if (scope === "cliente") {
            ultimaFacturaRegistrada = respuesta;
            $("acciones-factura-cliente").classList.remove("oculta");
            mostrarMensaje("mensaje-factura-cliente", "Factura guardada correctamente.", "exito");
            limpiarDetalles("cliente");
            await cargarHistorialCliente();
            await cargarProximoCodigo("codigo-cliente");
        } else {
            mostrarMensaje("mensaje-factura-admin", "Factura guardada correctamente.", "exito");
            cancelarEdicion();
            await cargarPanelAdministrador();
        }
    } catch (error) {
        mostrarMensaje(`mensaje-factura-${scope}`, mensajeError(error), "error");
    } finally {
        boton.disabled = false;
    }
}

// Carga el panel administrativo y sus estadísticas de facturas.
async function cargarPanelAdministrador() {
    try {
        facturasAdmin = await solicitar(API_FACTURAS);
        $("total-facturas").textContent = facturasAdmin.length;
        $("valor-total").textContent = formatoPesos(facturasAdmin.reduce((suma, factura) => suma + Number(factura.total || 0), 0));
        dibujarTablaFacturas();
        await cargarCatalogo();
        await cargarUsuariosAdmin();
        await cargarProximoCodigo("codigo-admin");
    } catch (error) {
        $("tabla-facturas-admin").innerHTML = `<tr><td colspan="5">${escaparHTML(mensajeError(error))}</td></tr>`;
    }
}

// Carga el historial y resumen de facturas del cliente.
async function cargarHistorialCliente() {
    try {
        const facturas = await solicitar(`${API_FACTURAS}/mis-facturas`);
        $("total-facturas-cliente").textContent = facturas.length;
        $("valor-total-cliente").textContent = formatoPesos(
            facturas.reduce((suma, factura) => suma + Number(factura.total || 0), 0)
        );
        $("tabla-facturas-cliente").innerHTML = facturas.length
            ? facturas.map((factura) => `
                <tr><td>${escaparHTML(factura.factura)}</td>
                <td>${escaparHTML(factura.fecha)}</td>
                <td>${formatoPesos(factura.total)}</td>
                <td><button class="button button-secondary" data-cliente-pdf="${factura.id}">Imprimir</button></td></tr>
            `).join("")
            : '<tr><td colspan="4">Aún no tienes facturas registradas.</td></tr>';
    } catch (error) {
        $("tabla-facturas-cliente").innerHTML =
            `<tr><td colspan="4">${escaparHTML(mensajeError(error))}</td></tr>`;
    }
}

// Carga la lista administrativa de clientes registrados.
async function cargarUsuariosAdmin() {
    try {
        usuariosAdmin = await solicitar(`${API_USUARIOS}/listar`);
        $("tabla-usuarios-admin").innerHTML = usuariosAdmin.length
            ? usuariosAdmin.map((usuario) => `
                <tr><td>${escaparHTML(usuario.nombre)}</td>
                <td>${escaparHTML(usuario.identificacion)}</td>
                <td>${usuario.cantidad_facturas}</td>
                <td>${formatoPesos(usuario.total_facturado)}</td>
                <td><button class="button button-secondary" data-usuario-accion="editar" data-id="${usuario.id}">Editar</button></td></tr>
            `).join("")
            : '<tr><td colspan="5">No hay clientes registrados.</td></tr>';
    } catch (error) {
        $("tabla-usuarios-admin").innerHTML =
            `<tr><td colspan="5">${escaparHTML(mensajeError(error))}</td></tr>`;
    }
}

// Edita los datos de un cliente mediante el formulario del navegador.
// Gestión administrativa de usuarios y facturas.
async function editarUsuario(id) {
    const usuario = usuariosAdmin.find((item) => Number(item.id) === id);
    if (!usuario) return;
    const nombre = window.prompt("Nombre del cliente:", usuario.nombre);
    if (nombre === null) return;
    const identificacion = window.prompt("Identificación:", usuario.identificacion);
    if (identificacion === null) return;
    try {
        await solicitar(`${API_USUARIOS}/${id}`, {
            method: "PUT",
            body: JSON.stringify({ nombre: nombre.trim(), identificacion: identificacion.trim() })
        });
        await cargarUsuariosAdmin();
    } catch (error) {
        window.alert(mensajeError(error));
    }
}

// Filtra y dibuja la tabla de facturas del administrador.
function dibujarTablaFacturas() {
    const filtro = $("buscar-admin").value.toLowerCase().trim();
    const filas = facturasAdmin.filter((factura) =>
        [factura.factura, factura.cliente, factura.fecha].some((valor) => String(valor || "").toLowerCase().includes(filtro))
    );
    $("tabla-facturas-admin").innerHTML = filas.length ? filas.map((factura) => `
        <tr><td>${escaparHTML(factura.factura)}</td><td>${escaparHTML(factura.cliente)}</td>
        <td>${escaparHTML(factura.fecha)}</td><td>${formatoPesos(factura.total)}</td><td>
        <button class="button button-secondary" data-accion="pdf" data-id="${factura.id}">PDF</button>
        <button class="button button-secondary" data-accion="editar" data-id="${factura.id}">Editar</button>
        <button class="button" data-accion="eliminar" data-id="${factura.id}">Eliminar</button></td></tr>
    `).join("") : '<tr><td colspan="5">No hay facturas para mostrar.</td></tr>';
}

// Carga una factura existente junto con sus productos para editarla.
async function editarFactura(id) {
    const factura = facturasAdmin.find((item) => Number(item.id) === id);
    if (!factura) return;
    idEditando = id;
    $("codigo-admin").value = factura.factura;
    $("nombre-factura-admin").value = factura.cliente;
    $("proveedor-factura-admin").value = factura.proveedor || "";
    $("nit-factura-admin").value = factura.nit_proveedor || "";
    $("fecha-admin").value = factura.fecha;
    $("titulo-formulario-admin").textContent = "Modificar factura";
    $("btn-guardar-admin").textContent = "Guardar cambios";
    $("btn-cancelar-edicion").classList.remove("oculta");
    const detalles = await solicitar(`${API_FACTURAS}/${id}/detalles`);
    cargarDetalles("admin", detalles);
    $("admin-facturas").scrollIntoView({ behavior: "smooth" });
}

// Cancela la edición y restablece el formulario administrativo.
function cancelarEdicion() {
    idEditando = null;
    $("form-factura-admin").reset();
    $("fecha-admin").value = fechaHoy();
    $("titulo-formulario-admin").textContent = "Registrar factura";
    $("btn-guardar-admin").textContent = "Guardar factura";
    $("btn-cancelar-edicion").classList.add("oculta");
    limpiarDetalles("admin");
    cargarProximoCodigo("codigo-admin");
}

// Cierra la sesión y devuelve la aplicación a la pantalla de ingreso.
async function cerrarSesion() {
    try { await solicitar(`${API_USUARIOS}/salir`, { method: "POST" }); } catch (error) { console.error(error); }
    sesion = null; facturasAdmin = []; productosCatalogo = []; usuariosAdmin = []; idEditando = null;
    mostrarVista("vista-ingreso");
}

// Conecta los botones laterales con el desplazamiento de navegación.
// Conexión de eventos de navegación y formularios.
function conectarNavegacion() {
    document.querySelectorAll(".nav-item").forEach((boton) => boton.addEventListener("click", () => {
        const destino = $(boton.dataset.target);
        boton.closest(".sidebar").querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
        boton.classList.add("active");
        destino?.scrollIntoView({ behavior: "smooth", block: "start" });
    }));
}

// Registra los eventos de botones, formularios y tablas.
function conectarEventos() {
    $("btn-mostrar-cliente").addEventListener("click", () => mostrarVista("vista-login-cliente"));
    $("btn-mostrar-admin").addEventListener("click", () => mostrarVista("vista-login-admin"));
    document.querySelectorAll("[data-volver]").forEach((boton) => boton.addEventListener("click", () => mostrarVista("vista-ingreso")));
    $("btn-ocr-cliente").addEventListener("click", () => analizarIA("cliente"));
    $("btn-ocr-admin").addEventListener("click", () => analizarIA("admin"));
    $("btn-ocr-local-cliente").addEventListener("click", () => analizarOCRLocal("cliente"));
    $("btn-ocr-local-admin").addEventListener("click", () => analizarOCRLocal("admin"));
    $("form-ingreso-cliente").addEventListener("submit", ingresarCliente);
    $("form-ingreso-admin").addEventListener("submit", ingresarAdmin);
    $("form-factura-cliente").addEventListener("submit", (evento) => registrarFactura("cliente", evento));
    $("form-factura-admin").addEventListener("submit", (evento) => registrarFactura("admin", evento));
    $("btn-agregar-detalle-cliente").addEventListener("click", () => agregarFilaDetalle("cliente"));
    $("btn-agregar-detalle").addEventListener("click", () => agregarFilaDetalle("admin"));
    $("btn-cancelar-edicion").addEventListener("click", cancelarEdicion);
    $("buscar-admin").addEventListener("input", dibujarTablaFacturas);
    $("btn-salir-cliente").addEventListener("click", cerrarSesion);
    $("btn-salir-admin").addEventListener("click", cerrarSesion);
    $("btn-abrir-catalogo").addEventListener("click", async () => {
        $("modal-catalogo").classList.remove("oculta");
        await cargarCatalogo();
    });
    $("btn-cerrar-catalogo").addEventListener("click", () => $("modal-catalogo").classList.add("oculta"));
    $("btn-abrir-usuarios").addEventListener("click", async () => {
        $("modal-usuarios").classList.remove("oculta");
        await cargarUsuariosAdmin();
    });
    $("btn-cerrar-usuarios").addEventListener("click", () => $("modal-usuarios").classList.add("oculta"));
    $("btn-abrir-finanzas").addEventListener("click", async () => {
        $("modal-finanzas").classList.remove("oculta"); await cargarFinanzas();
    });
    $("btn-cerrar-finanzas").addEventListener("click", () => $("modal-finanzas").classList.add("oculta"));
    $("btn-cargar-finanzas").addEventListener("click", cargarFinanzas);
    $("btn-finanzas-pdf").addEventListener("click", () => descargarInformeFinanciero("pdf"));
    $("btn-finanzas-excel").addEventListener("click", () => descargarInformeFinanciero("xlsx"));
    $("btn-borrar-todo").addEventListener("click", () => {
        if (window.confirm("Se conservarán los productos usados en facturas como inactivos. ¿Continuar?")) {
            borrarCatalogo("todos", [], "BORRAR TODO");
        }
    });
    $("btn-borrar-seleccionados").addEventListener("click", () => {
        const codigos = [...document.querySelectorAll(".producto-seleccionado:checked")]
            .map((control) => control.value);
        if (!codigos.length) {
            mostrarMensaje("mensaje-catalogo", "Selecciona al menos un producto.", "error");
            return;
        }
        if (window.confirm(`¿Borrar ${codigos.length} producto(s) seleccionado(s)?`)) {
            borrarCatalogo("seleccionados", codigos, "BORRAR SELECCIONADOS");
        }
    });
    $("lista-productos").addEventListener("click", (evento) => {
        const boton = evento.target.closest(".editar-producto");
        const agregar = evento.target.closest(".agregar-producto-factura");
        if (agregar) {
            agregarProductoDesdeCatalogo(agregar.dataset.codigo, "admin");
            $("admin-facturas").scrollIntoView({ behavior: "smooth" });
            return;
        }
        if (!boton) return;
        const producto = productosCatalogo.find((item) => String(item.codigo) === boton.dataset.codigo);
        if (!producto) return;
        $("producto-codigo").value = producto.codigo;
        $("producto-nombre").value = producto.nombre;
        $("producto-descripcion").value = producto.descripcion || "";
        $("producto-precio").value = producto.precio;
        $("producto-costo").value = producto.costo_adquisicion || 0;
        $("producto-iva").value = producto.iva_porcentaje || 0;
        $("producto-nombre").focus();
    });
    $("btn-imprimir-cliente").addEventListener("click", () => {
        if (ultimaFacturaRegistrada?.id) window.open(`${API_FACTURAS}/${ultimaFacturaRegistrada.id}/pdf`, "_blank", "noopener");
    });
    $("tabla-facturas-admin").addEventListener("click", async (evento) => {
        const boton = evento.target.closest("[data-accion]");
        if (!boton) return;
        const id = Number(boton.dataset.id);
        if (boton.dataset.accion === "pdf") window.open(`${API_FACTURAS}/${id}/pdf`, "_blank", "noopener");
        if (boton.dataset.accion === "editar") await editarFactura(id);
        if (boton.dataset.accion === "eliminar" && window.confirm("¿Eliminar esta factura?")) {
            await solicitar(`${API_FACTURAS}/${id}`, { method: "DELETE" });
            await cargarPanelAdministrador();
        }
    });
    $("tabla-facturas-cliente").addEventListener("click", (evento) => {
        const boton = evento.target.closest("[data-cliente-pdf]");
        if (boton) window.open(`${API_FACTURAS}/${boton.dataset.clientePdf}/pdf`, "_blank", "noopener");
    });
    $("tabla-usuarios-admin").addEventListener("click", async (evento) => {
        const boton = evento.target.closest("[data-usuario-accion]");
        if (!boton) return;
        const id = Number(boton.dataset.id);
        if (boton.dataset.usuarioAccion === "editar") await editarUsuario(id);
    });
    $("form-producto").addEventListener("submit", async (evento) => {
        evento.preventDefault();
        try {
            await solicitar(`${API_CATALOGO}/productos`, { method: "POST", body: JSON.stringify({
                codigo: $("producto-codigo").value.trim(), nombre: $("producto-nombre").value.trim(),
                descripcion: $("producto-descripcion").value.trim(), precio: Number($("producto-precio").value),
                costo_adquisicion: Number($("producto-costo").value),
                iva_porcentaje: Number($("producto-iva").value || 0)
            })});
            evento.currentTarget.reset();
            mostrarMensaje("mensaje-catalogo", "Producto guardado.", "exito");
            await cargarCatalogo();
        } catch (error) { mostrarMensaje("mensaje-catalogo", mensajeError(error), "error"); }
    });
    $("form-importar-productos").addEventListener("submit", async (evento) => {
        evento.preventDefault();
        const archivo = $("archivo-productos").files[0];
        if (!archivo) return;
        const formulario = new FormData(); formulario.append("archivo", archivo);
        try {
            const respuesta = await solicitar(`${API_CATALOGO}/importar`, { method: "POST", body: formulario });
            mostrarMensaje("mensaje-catalogo", `${respuesta.mensaje} Filas: ${respuesta.cantidad}.`, "exito");
            evento.currentTarget.reset();
            try {
                await cargarCatalogo();
            } catch (error) {
                mostrarMensaje("mensaje-catalogo", `Importación completada, pero no se pudo actualizar la lista: ${mensajeError(error)}`, "error");
            }
        } catch (error) {
            mostrarMensaje("mensaje-catalogo", mensajeError(error), "error");
        }
    });
    conectarNavegacion();
}

// Inicia sesión como cliente y carga su espacio de trabajo.
// Inicio y cierre de sesión.
async function ingresarCliente(evento) {
    evento.preventDefault();
    try {
        const datos = await solicitar(`${API_USUARIOS}/ingresar-cliente`, { method: "POST", body: JSON.stringify({
            nombre: $("nombre-ingreso").value.trim(), identificacion: $("identificacion-ingreso").value.trim()
        })});
        sesion = { autenticado: true, rol: "cliente", nombre: datos.nombre };
        $("saludo-cliente").textContent = `¡Bienvenido, ${sesion.nombre}!`;
        $("nombre-factura-cliente").value = sesion.nombre;
        mostrarVista("vista-cliente"); $("fecha-cliente").value = fechaHoy();
        limpiarDetalles("cliente"); await cargarCatalogo(); await cargarHistorialCliente(); await cargarProximoCodigo("codigo-cliente");
    } catch (error) { mostrarMensaje("mensaje-cliente", mensajeError(error), "error"); }
}

// Autentica al administrador y carga su panel de trabajo.
async function ingresarAdmin(evento) {
    evento.preventDefault();
    try {
        const datos = await solicitar(`${API_USUARIOS}/ingresar-admin`, { method: "POST", body: JSON.stringify({
            user: $("usuario-admin").value.trim(), contrasena: $("contrasena-admin").value
        })});
        sesion = { autenticado: true, rol: "admin", nombre: datos.nombre };
        $("saludo-admin").textContent = `Bienvenido, ${sesion.nombre}`;
        mostrarVista("vista-admin"); limpiarDetalles("admin"); await cargarPanelAdministrador();
    } catch (error) { mostrarMensaje("mensaje-admin", mensajeError(error), "error"); }
}

// Comprueba la sesión y prepara la interfaz inicial.
async function iniciarAplicacion() {
    conectarEventos();
    try {
        const datos = await solicitar(`${API_USUARIOS}/sesion`);
        if (!datos.autenticado) return mostrarVista("vista-ingreso");
        sesion = datos;
        if (sesion.rol === "admin") {
            $("saludo-admin").textContent = `Bienvenido, ${sesion.nombre}`;
            mostrarVista("vista-admin"); limpiarDetalles("admin"); await cargarPanelAdministrador();
        } else {
            $("saludo-cliente").textContent = `¡Bienvenido, ${sesion.nombre}!`;
            $("nombre-factura-cliente").value = sesion.nombre;
            mostrarVista("vista-cliente"); $("fecha-cliente").value = fechaHoy();
            limpiarDetalles("cliente"); await cargarCatalogo(); await cargarHistorialCliente(); await cargarProximoCodigo("codigo-cliente");
        }
    } catch (error) { console.error(error); mostrarVista("vista-ingreso"); }
}

iniciarAplicacion();
