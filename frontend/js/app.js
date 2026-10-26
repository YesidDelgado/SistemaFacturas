const API_URL = "/facturas";

let facturas = [];
let idFacturaEditando = null;

const formulario = document.getElementById("form-factura");
const campoFactura = document.getElementById("factura");
const campoCliente = document.getElementById("cliente");
const campoFecha = document.getElementById("fecha");
const campoTotal = document.getElementById("total");

const tablaFacturas = document.getElementById("tabla-facturas");
const campoBuscar = document.getElementById("buscar");
const mensaje = document.getElementById("mensaje");

const botonGuardar = document.getElementById("btn-guardar");
const botonCancelar = document.getElementById("btn-cancelar");


function escaparHTML(valor) {
    return String(valor ?? "").replace(/[&<>"']/g, caracter => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[caracter]);
}


function formatearMoneda(valor) {
    return new Intl.NumberFormat("es-CO", {
        style: "currency",
        currency: "COP"
    }).format(Number(valor) || 0);
}


async function solicitarAPI(url, opciones = {}) {
    const respuesta = await fetch(url, {
        ...opciones,
        headers: {
            "Content-Type": "application/json",
            ...(opciones.headers || {})
        }
    });

    if (!respuesta.ok) {
        let detalle = "No fue posible procesar la solicitud.";

        try {
            const error = await respuesta.json();
            detalle = error.detail || detalle;
        } catch {
            // La respuesta no siempre contiene JSON.
        }

        throw new Error(
            typeof detalle === "string"
                ? detalle
                : JSON.stringify(detalle)
        );
    }

    if (respuesta.status === 204) {
        return null;
    }

    return respuesta.json();
}


// Muestra el siguiente código disponible en el formulario.
async function actualizarCodigoSiguiente() {
    try {
        const resultado = await solicitarAPI(
            `${API_URL}/proximo-codigo`
        );

        if (idFacturaEditando === null) {
            campoFactura.value = resultado.factura;
        }
    } catch (error) {
        campoFactura.value = "No disponible";
        console.error("Error al consultar el código:", error);
    }
}


// Carga las facturas y actualiza los indicadores.
async function cargarFacturas() {
    try {
        facturas = await solicitarAPI(API_URL);

        document.getElementById("estado-api").textContent =
            "API conectada correctamente";

        mostrarFacturas();
        actualizarResumen();
        await actualizarCodigoSiguiente();

    } catch (error) {
        document.getElementById("estado-api").textContent =
            "Error de conexión";

        tablaFacturas.innerHTML = `
            <tr>
                <td colspan="5">${escaparHTML(error.message)}</td>
            </tr>
        `;
    }
}


// Dibuja la tabla y aplica el filtro de búsqueda.
function mostrarFacturas() {
    const busqueda = campoBuscar.value.trim().toLowerCase();

    const filtradas = facturas.filter(factura =>
        String(factura.factura).toLowerCase().includes(busqueda) ||
        String(factura.cliente).toLowerCase().includes(busqueda)
    );

    if (filtradas.length === 0) {
        tablaFacturas.innerHTML = `
            <tr>
                <td colspan="5">No hay facturas para mostrar.</td>
            </tr>
        `;
        return;
    }

    tablaFacturas.innerHTML = filtradas.map(factura => `
        <tr>
            <td>${escaparHTML(factura.factura)}</td>
            <td>${escaparHTML(factura.cliente)}</td>
            <td>${escaparHTML(factura.fecha)}</td>
            <td>${formatearMoneda(factura.total)}</td>
            <td>
                <button
                type="button"
                data-accion="imprimir"
                data-id="${factura.id}"
                >Imprimir</button>

                <button
                type="button"
                class="secundario"
                data-accion="pdf"
                data-id="${factura.id}"
                >PDF</button>

                <button
                    type="button"
                    data-accion="editar"
                    data-id="${factura.id}"
                >Editar</button>

                <button
                    type="button"
                    data-accion="eliminar"
                    data-id="${factura.id}"
                >Eliminar</button>
            </td>
        </tr>
    `).join("");
}


// Calcula la cantidad y el valor acumulado.
function actualizarResumen() {
    document.getElementById("total-facturas").textContent =
        facturas.length;

    const suma = facturas.reduce(
        (acumulado, factura) =>
            acumulado + Number(factura.total),
        0
    );

    document.getElementById("valor-total").textContent =
        formatearMoneda(suma);
}


// Restablece el formulario.
function reiniciarFormulario() {
    formulario.reset();

    idFacturaEditando = null;
    campoFactura.value = "";

    document.getElementById("titulo-formulario").textContent =
        "Registrar factura";

    botonGuardar.textContent = "Guardar factura";
    botonCancelar.hidden = true;
}


// Registra o actualiza una factura.
formulario.addEventListener("submit", async evento => {
    evento.preventDefault();

    const datosFactura = {
        cliente: campoCliente.value.trim(),
        fecha: campoFecha.value,
        total: Number(campoTotal.value)
    };

    if (
        !datosFactura.cliente ||
        !datosFactura.fecha ||
        !Number.isFinite(datosFactura.total) ||
        datosFactura.total < 0
    ) {
        mensaje.textContent = "Verifica los datos ingresados.";
        return;
    }

    const editando = idFacturaEditando !== null;

    const url = editando
        ? `${API_URL}/${idFacturaEditando}`
        : API_URL;

    const metodo = editando ? "PUT" : "POST";

    botonGuardar.disabled = true;
    mensaje.textContent = "Guardando factura...";

    try {
        const resultado = await solicitarAPI(url, {
            method: metodo,
            body: JSON.stringify(datosFactura)
        });

        reiniciarFormulario();

        await cargarFacturas();

        mensaje.textContent = editando
            ? `Factura ${resultado.factura} actualizada correctamente.`
            : `Factura ${resultado.factura} creada correctamente.`;

    } catch (error) {
        mensaje.textContent = error.message;

    } finally {
        botonGuardar.disabled = false;
    }
});


// Filtra al escribir en la búsqueda.
campoBuscar.addEventListener("input", mostrarFacturas);


// Gestiona las acciones de la tabla.
tablaFacturas.addEventListener("click", async evento => {
    const boton = evento.target.closest("button[data-accion]");

    if (!boton) {
        return;
    }

    const id = Number(boton.dataset.id);
    const accion = boton.dataset.accion;

    if (accion === "imprimir") {
        window.open(`${API_URL}/${id}/pdf`, "_blank");
        return;
        }

    if (accion === "pdf") {
        window.location.href = `${API_URL}/${id}/pdf?descargar=true`;
        return;
        }

    if (accion === "editar") {
        const factura = facturas.find(item => item.id === id);

        if (!factura) {
            return;
        }

        idFacturaEditando = factura.id;

        campoFactura.value = factura.factura;
        campoCliente.value = factura.cliente;
        campoFecha.value = factura.fecha;
        campoTotal.value = factura.total;

        document.getElementById("titulo-formulario").textContent =
            `Editar ${factura.factura}`;

        botonGuardar.textContent = "Guardar cambios";
        botonCancelar.hidden = false;

        mensaje.textContent = "";

        formulario.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }

    if (accion === "eliminar") {
        const factura = facturas.find(item => item.id === id);

        if (!factura) {
            return;
        }

        if (!window.confirm(
            `¿Deseas eliminar la factura ${factura.factura}?`
        )) {
            return;
        }

        try {
            await solicitarAPI(`${API_URL}/${id}`, {
                method: "DELETE"
            });

            if (idFacturaEditando === id) {
                reiniciarFormulario();
            }

            await cargarFacturas();

            mensaje.textContent =
                `Factura ${factura.factura} eliminada correctamente.`;

        } catch (error) {
            mensaje.textContent = error.message;
        }
    }
});


// Cancela la edición.
botonCancelar.addEventListener("click", () => {
    reiniciarFormulario();
    actualizarCodigoSiguiente();
    mensaje.textContent = "Edición cancelada.";
});


// Inicio de la aplicación.
cargarFacturas();