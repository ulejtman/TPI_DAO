document.querySelectorAll('[data-imprimir]').forEach(button => button.addEventListener('click', () => window.print()));
const add = document.querySelector('[data-agregar]');
if (add) {
  const total = document.querySelector('#id_lineas-TOTAL_FORMS');
  const container = document.querySelector('[data-renglones]');
  add.addEventListener('click', () => {
    const index = Number(total.value);
    if (index >= 100) return;
    const fragment = document.querySelector('#renglon-vacio').innerHTML.replaceAll('__prefix__', index);
    container.insertAdjacentHTML('beforeend', fragment);
    total.value = index + 1;
    container.lastElementChild.querySelector('select, input')?.focus();
    actualizarVenta();
  });
  container.addEventListener('click', event => {
    if (!event.target.matches('[data-quitar]')) return;
    const row = event.target.closest('.renglon');
    if (row === container.lastElementChild) {
      row.remove();
      total.value = Number(total.value) - 1;
      add.focus();
      actualizarVenta();
    }
  });
}

function actualizarVenta() {
  const data = document.querySelector('#productos-venta');
  if (!data) return;
  const productos = JSON.parse(data.textContent);
  const formato = cents => new Intl.NumberFormat('es-AR', {style: 'currency', currency: 'ARS'}).format(cents / 100);
  let total = 0;
  document.querySelectorAll('[data-renglones] .renglon').forEach(row => {
    const selector = row.querySelector('select');
    const cantidad = row.querySelector('input[type=number]');
    const producto = productos[selector?.value];
    let resumen = row.querySelector('[data-resumen]');
    if (!resumen) {
      resumen = document.createElement('p');
      resumen.className = 'nota linea-resumen';
      resumen.dataset.resumen = '';
      row.appendChild(resumen);
    }
    if (producto) {
      const unidades = Math.max(0, Number(cantidad?.value) || 0);
      total += producto.precio * unidades;
      resumen.textContent = `${formato(producto.precio)} por unidad · ${producto.stock} disponibles en tu local · Subtotal ${formato(producto.precio * unidades)}`;
    } else resumen.textContent = 'Seleccioná un producto para consultar precio y disponible.';
  });
  document.querySelector('[data-total-venta]').textContent = formato(total);
}
document.querySelector('[data-renglones]')?.addEventListener('input', actualizarVenta);
document.querySelector('[data-renglones]')?.addEventListener('change', actualizarVenta);
actualizarVenta();
