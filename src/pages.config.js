import Dashboard from './pages/Dashboard';
import Cotizacion from './pages/Cotizacion';
import Pedidos from './pages/Pedidos';
import Facturacion from './pages/Facturacion';
import __Layout from './Layout.jsx';

export const PAGES = {
"Dashboard": Dashboard,
"Cotizacion": Cotizacion,
"Pedidos": Pedidos,
"Facturacion": Facturacion,
}

export const pagesConfig = {
mainPage: "Dashboard",
Pages: PAGES,
Layout: __Layout,
};