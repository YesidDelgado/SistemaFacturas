"use strict";

// Rutas de la API
const API_FACTURAS = "/facturas";
const API_USUARIOS = "/usuarios";
const API_IA = "/ia";

// Estado de la sesión actual
let sesion = null;
let facturasAdmin = [];
let idEditando = null;
let ultimaFacturaRegistrada = null;

// Elementos auxiliares
const $ = (id) => document.getElementById(id);

const vistas = [
    "vista-ingreso",
    "vista-login-cliente",
    "vista-login-admin",
    "vista-cliente",
    "vista-admin"
];

// Mostrar una vista y ocultar las demás
function mostrarVista(idVista) {
    vistas.forEach((id) => $(id).classList.add("oculta"));
    $(idVista).classList.remove("oculta");
    window.scrollTo({ top: 0, behavior: "smooth" });
}

// Mostrar mensajes de éxito o error
function mostrarMensaje(id, texto, tipo = "") {
    const elemento = $(id);
    elemento.textContent = texto;
    elemento.className = `mensaje ${tipo}`.trim();
}

// Petición común a la API.
// IMPORTANTE: FormData no debe llevar Content-Type manual.
// El navegador genera automáticamente el multipart/form-data.
async function solicitar(url, opciones = {}) {
    const esFormData = opciones.body instanceof FormData;

    const headers = {
        ...(opciones.body && !esFormData
            ? { "Content-Type": "application/json" }
            : {}),
        ...(opciones.headers || {})
    };

    const respuesta = await fetch(url, {
        credentials: "same-origin",
        ...opciones,
        headers
    });

    const texto = await respuesta.text();
    let datos = {};

    if (texto) {
        try {
            datos = JSON.parse(texto);
        } catch {
            datos = { detail: texto };
        }
    }

    if (!respuesta.ok) {
        const detalle =
            datos.detail ||
            datos.mensaje ||
            "Ocurrió un error.";

        throw new Error(
            typeof detalle === "string"
                ? detalle
                : JSON.stringify(detalle)
        );
    }

    return datos;
}

// Convierte errores de red en mensajes comprensibles
function mensajeError(error) {
    if (error instanceof TypeError) {
        return "No se pudo conectar con el servidor. Comprueba que la API esté activa.";
    }

    return error.message || "Ocurrió un error inesperado.";
}

// Fecha local en formato YYYY-MM-DD
function fechaHoy() {
    const fecha = new Date();

    const local = new Date(
        fecha.getTime() - fecha.getTimezoneOffset() * 60000
    );

    return local.toISOString().slice(0, 10);
}

// Formato de moneda colombiana
function formatoPesos(valor) {
    return new Intl.NumberFormat("es-CO", {
        style: "currency",
        currency: "COP",
        maximumFractionDigits: 2
    }).format(Number(valor) || 0);
}

// Habilitar la impresión únicamente después de registrar una factura.
function habilitarImpresionCliente(factura) {
    ultimaFacturaRegistrada = factura;

    $("acciones-factura-cliente").classList.remove("oculta");
    $("btn-imprimir-cliente").disabled = false;
}

// Ocultar el botón cuando todavía no hay una factura registrada.
function deshabilitarImpresionCliente() {
    ultimaFacturaRegistrada = null;

    $("acciones-factura-cliente").classList.add("oculta");
    $("btn-imprimir-cliente").disabled = true;
}

// Obtener el próximo consecutivo generado por el backend
async function cargarProximoCodigo(idCampo) {
    const campo = $(idCampo);
    campo.value = "Generando...";

    try {
        const datos = await solicitar(`${API_FACTURAS}/proximo-codigo`);

        const codigo =
            datos.factura ||
            datos.codigo ||
            datos.proximo_codigo ||
            datos.numero_factura;

        if (codigo) {
            campo.value = codigo;
        } else {
            campo.value = "";
            console.error("Respuesta de próximo código:", datos);
        }
    } catch (error) {
        campo.value = "";
        console.error("No se pudo obtener el consecutivo:", error);
    }
}

// ======================================================
// ANÁLISIS DE FACTURAS MEDIANTE IA / OCR
// ======================================================

// Envía un PDF o imagen al backend para extraer los datos.
// Esta función NO registra la factura.
async function analizarFacturaOCR(
    idArchivo,
    idBoton,
    idMensaje,
    idCampoCliente,
    idCampoFecha,
    idCampoTotal
) {
    // Validar sesión y rol
    if (
        !sesion ||
        !["cliente", "admin"].includes(sesion.rol)
    ) {
        mostrarVista("vista-ingreso");
        return;
    }

    const campoArchivo = $(idArchivo);
    const boton = $(idBoton);
    const archivo = campoArchivo.files[0];

    if (!archivo) {
        mostrarMensaje(
            idMensaje,
            "Selecciona primero un archivo PDF o una imagen.",
            "error"
        );
        return;
    }

    // Validar extensiones permitidas
    const extensionesPermitidas = [
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp"
    ];

    const nombreArchivo = archivo.name.toLowerCase();

    const extensionValida = extensionesPermitidas.some(
        (extension) => nombreArchivo.endsWith(extension)
    );

    if (!extensionValida) {
        mostrarMensaje(
            idMensaje,
            "Formato no permitido. Usa PDF, PNG, JPG, JPEG o WEBP.",
            "error"
        );
        return;
    }

    // Límite de 10 MB
    const limiteBytes = 10 * 1024 * 1024;

    if (archivo.size > limiteBytes) {
        mostrarMensaje(
            idMensaje,
            "El archivo supera el límite permitido de 10 MB.",
            "error"
        );
        return;
    }

    // Preparar archivo para enviarlo al backend
    const formulario = new FormData();

    // El nombre "archivo" debe coincidir con el parámetro
    // UploadFile declarado en backend/routers/ia.py.
    formulario.append("archivo", archivo);

    boton.disabled = true;
    mostrarMensaje(
        idMensaje,
        "Analizando el documento. Esto puede tardar unos segundos..."
    );

    try {
        const respuesta = await solicitar(
            `${API_IA}/analizar-factura`,
            {
                method: "POST",
                body: formulario
            }
        );

        const datos = respuesta.datos || {};

        // Solo completar los campos que el análisis haya reconocido.
        // El código interno de factura nunca se modifica aquí.
        if (
            datos.cliente !== undefined &&
            datos.cliente !== null
        ) {
            $(idCampoCliente).value = datos.cliente;
        }

        if (
            datos.fecha !== undefined &&
            datos.fecha !== null
        ) {
            $(idCampoFecha).value = datos.fecha;
        }

        if (
            datos.total !== undefined &&
            datos.total !== null
        ) {
            $(idCampoTotal).value = datos.total;
        }

        mostrarMensaje(
            idMensaje,
            respuesta.mensaje ||
                "Análisis terminado. Revisa los datos antes de registrar la factura.",
            "exito"
        );
    } catch (error) {
        mostrarMensaje(
            idMensaje,
            `No fue posible analizar el documento: ${mensajeError(error)}`,
            "error"
        );
    } finally {
        boton.disabled = false;
    }
}

// ======================================================
// BOTONES DE ANÁLISIS OCR
// ======================================================

// OCR del cliente
$("btn-ocr-cliente").addEventListener("click", () => {
    analizarFacturaOCR(
        "archivo-ocr-cliente",
        "btn-ocr-cliente",
        "mensaje-ocr-cliente",
        "nombre-factura-cliente",
        "fecha-cliente",
        "valor-cliente"
    );
});

// OCR del administrador
$("btn-ocr-admin").addEventListener("click", () => {
    analizarFacturaOCR(
        "archivo-ocr-admin",
        "btn-ocr-admin",
        "mensaje-ocr-admin",
        "nombre-factura-admin",
        "fecha-admin",
        "valor-admin"
    );
});

// Limpiar mensajes de ingreso
function limpiarMensajesIngreso() {
    mostrarMensaje("mensaje-ingreso", "");
    mostrarMensaje("mensaje-cliente", "");
    mostrarMensaje("mensaje-admin", "");
}

// Botones de la pantalla inicial
$("btn-mostrar-cliente").addEventListener("click", () => {
    limpiarMensajesIngreso();
    $("form-ingreso-cliente").reset();
    mostrarVista("vista-login-cliente");
});

$("btn-mostrar-admin").addEventListener("click", () => {
    limpiarMensajesIngreso();
    $("form-ingreso-admin").reset();
    mostrarVista("vista-login-admin");
});

document.querySelectorAll("[data-volver]").forEach((boton) => {
    boton.addEventListener("click", () => {
        mostrarVista("vista-ingreso");
    });
});

// ======================================================
// INGRESO DE CLIENTE
// ======================================================

$("form-ingreso-cliente").addEventListener("submit", async (evento) => {
    evento.preventDefault();

    const boton = evento.currentTarget.querySelector(
        'button[type="submit"]'
    );

    boton.disabled = true;
    mostrarMensaje("mensaje-cliente", "Validando datos...");

    const nombre = $("nombre-ingreso").value.trim();
    const identificacion = $("identificacion-ingreso").value.trim();

    try {
        const datos = await solicitar(
            `${API_USUARIOS}/ingresar-cliente`,
            {
                method: "POST",
                body: JSON.stringify({
                    nombre,
                    identificacion
                })
            }
        );

        sesion = {
            autenticado: true,
            rol: "cliente",
            nombre: datos.nombre || nombre,
            usuario_id: datos.usuario_id
        };

        $("saludo-cliente").textContent =
            `¡Bienvenido, ${sesion.nombre}!`;

        deshabilitarImpresionCliente();
        mostrarVista("vista-cliente");

        mostrarMensaje(
            "mensaje-factura-cliente",
            datos.mensaje ||
                `Bienvenido, ${sesion.nombre}. Registra tus facturas.`,
            "exito"
        );

        $("form-factura-cliente").reset();
        $("fecha-cliente").value = fechaHoy();

        // Limpiar el archivo y el mensaje del OCR
        $("archivo-ocr-cliente").value = "";
        mostrarMensaje("mensaje-ocr-cliente", "");

        await cargarProximoCodigo("codigo-cliente");
    } catch (error) {
        mostrarMensaje(
            "mensaje-cliente",
            mensajeError(error),
            "error"
        );
    } finally {
        boton.disabled = false;
    }
});

// ======================================================
// INGRESO DE ADMINISTRADOR
// ======================================================

$("form-ingreso-admin").addEventListener("submit", async (evento) => {
    evento.preventDefault();

    const boton = evento.currentTarget.querySelector(
        'button[type="submit"]'
    );

    boton.disabled = true;
    mostrarMensaje("mensaje-admin", "Validando credenciales...");

    const user = $("usuario-admin").value.trim();
    const contrasena = $("contrasena-admin").value;

    try {
        const datos = await solicitar(
            `${API_USUARIOS}/ingresar-admin`,
            {
                method: "POST",
                body: JSON.stringify({
                    user,
                    contrasena
                })
            }
        );

        sesion = {
            autenticado: true,
            rol: "admin",
            nombre: datos.nombre || user
        };

        $("saludo-admin").textContent =
            `Bienvenido, ${sesion.nombre}`;

        mostrarVista("vista-admin");
        await cargarPanelAdministrador();
    } catch (error) {
        mostrarMensaje(
            "mensaje-admin",
            mensajeError(error),
            "error"
        );
    } finally {
        boton.disabled = false;
    }
});

// ======================================================
// REGISTRAR FACTURA COMO CLIENTE
// ======================================================

$("form-factura-cliente").addEventListener(
    "submit",
    async (evento) => {
        evento.preventDefault();

        if (!sesion || sesion.rol !== "cliente") {
            mostrarVista("vista-ingreso");
            return;
        }

        const boton = $("btn-registrar-cliente");
        boton.disabled = true;

        const datosFactura = {
            cliente: $("nombre-factura-cliente").value.trim(),
            fecha: $("fecha-cliente").value,
            total: Number($("valor-cliente").value)
        };

        try {
            const respuesta = await solicitar(API_FACTURAS, {
                method: "POST",
                body: JSON.stringify(datosFactura)
            });

            // Conservar los datos devueltos por el backend para imprimir.
            ultimaFacturaRegistrada = respuesta;
            habilitarImpresionCliente(respuesta);

            mostrarMensaje(
                "mensaje-factura-cliente",
                `Factura ${respuesta.factura || ""} registrada correctamente. Ya puedes imprimirla.`,
                "exito"
            );

            $("form-factura-cliente").reset();
            $("fecha-cliente").value = fechaHoy();

            $("archivo-ocr-cliente").value = "";
            mostrarMensaje("mensaje-ocr-cliente", "");

            await cargarProximoCodigo("codigo-cliente");
        } catch (error) {
            mostrarMensaje(
                "mensaje-factura-cliente",
                mensajeError(error),
                "error"
            );
        } finally {
            boton.disabled = false;
        }
    }
);

// ======================================================
// REGISTRAR O ACTUALIZAR FACTURA COMO ADMINISTRADOR
// ======================================================

$("form-factura-admin").addEventListener(
    "submit",
    async (evento) => {
        evento.preventDefault();

        if (!sesion || sesion.rol !== "admin") {
            mostrarVista("vista-ingreso");
            return;
        }

        const boton = $("btn-guardar-admin");
        boton.disabled = true;

        const datosFactura = {
            cliente: $("nombre-factura-admin").value.trim(),
            fecha: $("fecha-admin").value,
            total: Number($("valor-admin").value)
        };

        try {
            if (idEditando !== null) {
                await solicitar(`${API_FACTURAS}/${idEditando}`, {
                    method: "PUT",
                    body: JSON.stringify(datosFactura)
                });

                mostrarMensaje(
                    "mensaje-factura-admin",
                    "Factura modificada correctamente.",
                    "exito"
                );
            } else {
                await solicitar(API_FACTURAS, {
                    method: "POST",
                    body: JSON.stringify(datosFactura)
                });

                mostrarMensaje(
                    "mensaje-factura-admin",
                    "Factura registrada correctamente.",
                    "exito"
                );
            }

            cancelarEdicion();
            await cargarPanelAdministrador();
        } catch (error) {
            mostrarMensaje(
                "mensaje-factura-admin",
                mensajeError(error),
                "error"
            );
        } finally {
            boton.disabled = false;
        }
    }
);

// ======================================================
// PANEL DE ADMINISTRACIÓN
// ======================================================

// Cargar estadísticas y facturas del administrador
async function cargarPanelAdministrador() {
    try {
        const datos = await solicitar(API_FACTURAS);

        facturasAdmin = Array.isArray(datos)
            ? datos
            : (datos.facturas || []);

        $("total-facturas").textContent = facturasAdmin.length;

        const acumulado = facturasAdmin.reduce(
            (suma, factura) =>
                suma + (Number(factura.total) || 0),
            0
        );

        $("valor-total").textContent = formatoPesos(acumulado);

        dibujarTablaFacturas();
        await cargarProximoCodigo("codigo-admin");
    } catch (error) {
        $("tabla-facturas-admin").innerHTML =
            `<tr><td colspan="5">No se pudieron cargar las facturas: ${
                escaparHTML(mensajeError(error))
            }</td></tr>`;
    }
}

// Evitar insertar datos recibidos como HTML
function escaparHTML(valor) {
    return String(valor ?? "").replace(/[&<>"']/g, (caracter) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[caracter]);
}

// Dibujar la tabla de administración
function dibujarTablaFacturas() {
    const filtro = $("buscar-admin").value.trim().toLowerCase();

    const filtradas = facturasAdmin.filter((factura) => {
        return [
            factura.factura,
            factura.cliente,
            factura.fecha
        ].some((valor) =>
            String(valor ?? "").toLowerCase().includes(filtro)
        );
    });

    const tabla = $("tabla-facturas-admin");

    if (!filtradas.length) {
        tabla.innerHTML =
            '<tr><td colspan="5">No hay facturas para mostrar.</td></tr>';
        return;
    }

    tabla.innerHTML = filtradas.map((factura) => `
        <tr>
            <td>${escaparHTML(factura.factura)}</td>
            <td>${escaparHTML(factura.cliente)}</td>
            <td>${escaparHTML(factura.fecha)}</td>
            <td>${formatoPesos(factura.total)}</td>
            <td>
                <button type="button" data-accion="pdf"
                    data-id="${Number(factura.id)}">PDF / Imprimir</button>
                <button type="button" data-accion="editar"
                    data-id="${Number(factura.id)}">Modificar</button>
                <button type="button" data-accion="eliminar"
                    data-id="${Number(factura.id)}">Eliminar</button>
            </td>
        </tr>
    `).join("");
}

// Buscar en la tabla
$("buscar-admin").addEventListener("input", dibujarTablaFacturas);

// Acciones de la tabla
$("tabla-facturas-admin").addEventListener(
    "click",
    async (evento) => {
        const boton = evento.target.closest("button[data-accion]");

        if (!boton) return;

        if (!sesion || sesion.rol !== "admin") {
            mostrarVista("vista-ingreso");
            return;
        }

        const id = Number(boton.dataset.id);
        const accion = boton.dataset.accion;

        const factura = facturasAdmin.find(
            (item) => Number(item.id) === id
        );

        if (!factura) return;

        if (accion === "pdf") {
            window.open(
                `${API_FACTURAS}/${id}/pdf`,
                "_blank",
                "noopener"
            );
            return;
        }

        if (accion === "editar") {
            idEditando = id;

            $("codigo-admin").value = factura.factura || "";
            $("nombre-factura-admin").value = factura.cliente || "";
            $("fecha-admin").value = factura.fecha || "";
            $("valor-admin").value = factura.total ?? "";

            $("titulo-formulario-admin").textContent =
                "Modificar factura";

            $("btn-guardar-admin").textContent = "Guardar cambios";

            $("btn-cancelar-edicion").classList.remove("oculta");

            mostrarMensaje("mensaje-factura-admin", "");

            $("form-factura-admin").scrollIntoView({
                behavior: "smooth"
            });

            return;
        }

        if (accion === "eliminar") {
            const confirmar = window.confirm(
                `¿Seguro que deseas eliminar la factura ${factura.factura}?`
            );

            if (!confirmar) return;

            try {
                await solicitar(`${API_FACTURAS}/${id}`, {
                    method: "DELETE"
                });

                mostrarMensaje(
                    "mensaje-factura-admin",
                    "Factura eliminada correctamente.",
                    "exito"
                );

                if (idEditando === id) {
                    cancelarEdicion();
                }

                await cargarPanelAdministrador();
            } catch (error) {
                mostrarMensaje(
                    "mensaje-factura-admin",
                    mensajeError(error),
                    "error"
                );
            }
        }
    }
);

// Cancelar una modificación
function cancelarEdicion() {
    idEditando = null;

    $("form-factura-admin").reset();
    $("fecha-admin").value = fechaHoy();

    $("titulo-formulario-admin").textContent = "Registrar factura";
    $("btn-guardar-admin").textContent = "Registrar factura";

    $("btn-cancelar-edicion").classList.add("oculta");

    $("archivo-ocr-admin").value = "";
    mostrarMensaje("mensaje-ocr-admin", "");

    cargarProximoCodigo("codigo-admin");
}

$("btn-cancelar-edicion").addEventListener(
    "click",
    cancelarEdicion
);

// ======================================================
// CERRAR SESIÓN
// ======================================================

async function cerrarSesion() {
    try {
        await solicitar(`${API_USUARIOS}/salir`, {
            method: "POST"
        });
    } catch (error) {
        console.error(
            "No se pudo confirmar el cierre de sesión:",
            error
        );
    }

    sesion = null;
    facturasAdmin = [];
    idEditando = null;

    $("form-ingreso-cliente").reset();
    $("form-ingreso-admin").reset();
    $("form-factura-cliente").reset();
    $("form-factura-admin").reset();

    $("archivo-ocr-cliente").value = "";
    $("archivo-ocr-admin").value = "";

    mostrarMensaje("mensaje-ocr-cliente", "");
    mostrarMensaje("mensaje-ocr-admin", "");

    deshabilitarImpresionCliente();
    mostrarVista("vista-ingreso");
}

$("btn-salir-cliente").addEventListener("click", cerrarSesion);
$("btn-salir-admin").addEventListener("click", cerrarSesion);

// ======================================================
// RECUPERAR SESIÓN AL ABRIR LA PÁGINA
// ======================================================

async function iniciarAplicacion() {
    try {
        const datos = await solicitar(`${API_USUARIOS}/sesion`);

        if (!datos.autenticado) {
            mostrarVista("vista-ingreso");
            return;
        }

        sesion = datos;

        if (sesion.rol === "admin") {
            $("saludo-admin").textContent =
                `Bienvenido, ${sesion.nombre || "administrador"}`;

            mostrarVista("vista-admin");
            await cargarPanelAdministrador();
        } else if (sesion.rol === "cliente") {
            $("saludo-cliente").textContent =
                `¡Bienvenido, ${sesion.nombre || "cliente"}!`;

            mostrarVista("vista-cliente");
            $("fecha-cliente").value = fechaHoy();

            await cargarProximoCodigo("codigo-cliente");
        } else {
            mostrarVista("vista-ingreso");
        }
    } catch (error) {
        console.error("No se pudo recuperar la sesión:", error);
        mostrarVista("vista-ingreso");
    }
}

// Imprimir la factura registrada por el cliente
$("btn-imprimir-cliente").addEventListener("click", () => {
    if (!ultimaFacturaRegistrada || !ultimaFacturaRegistrada.id) {
        return;
    }

    window.open(
        `${API_FACTURAS}/${Number(ultimaFacturaRegistrada.id)}/pdf`,
        "_blank",
        "noopener"
    );
});

// Iniciar la aplicación
iniciarAplicacion();