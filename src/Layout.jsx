import React from "react";
import { Link, useLocation } from "react-router-dom";
import { createPageUrl } from "@/utils";
import { LayoutDashboard, Calculator, Package, FileText, LogOut } from "lucide-react";
import { useAuth } from "@/lib/AuthContext";
import {
Sidebar,
SidebarContent,
SidebarGroup,
SidebarGroupContent,
SidebarGroupLabel,
SidebarMenu,
SidebarMenuButton,
SidebarMenuItem,
SidebarHeader,
SidebarFooter,
SidebarProvider,
SidebarTrigger,
} from "@/components/ui/sidebar";

const navigationItems = [
{
title: "Dashboard",
url: createPageUrl("Dashboard"),
icon: LayoutDashboard,
},
{
title: "Cotización",
url: createPageUrl("Cotizacion"),
icon: Calculator,
},
{
title: "Pedidos",
url: createPageUrl("Pedidos"),
icon: Package,
},
{
title: "Facturación",
url: createPageUrl("Facturacion"),
icon: FileText,
},
];

export default function Layout({ children, currentPageName }) {
const location = useLocation();
const { user, logout } = useAuth();

return (
<SidebarProvider>
<div className="min-h-screen flex w-full bg-gradient-to-br from-slate-50 to-slate-100">
<Sidebar className="border-r border-slate-200 bg-white">
<SidebarHeader className="border-b border-slate-200 p-4">
<div className="flex items-center justify-center">
  <img
    src="/logo.jpeg"
    alt="Master Partes"
    className="h-12 w-auto object-contain"
  />
</div>
</SidebarHeader>

<SidebarContent className="p-3">
<SidebarGroup>
<SidebarGroupLabel className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-3 py-2">
Módulos
</SidebarGroupLabel>
<SidebarGroupContent>
<SidebarMenu>
{navigationItems.map((item) => {
const isActive = location.pathname === item.url;
return (
<SidebarMenuItem key={item.title}>
<SidebarMenuButton
asChild
className={`transition-all duration-200 rounded-xl mb-1 ${
isActive
? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-md hover:shadow-lg'
: 'hover:bg-slate-100 text-slate-700'
}`}
>
<Link to={item.url} className="flex items-center gap-3 px-4 py-3">
<item.icon className="w-5 h-5" />
<span className="font-medium">{item.title}</span>
</Link>
</SidebarMenuButton>
</SidebarMenuItem>
);
})}
</SidebarMenu>
</SidebarGroupContent>
</SidebarGroup>
</SidebarContent>

<SidebarFooter className="border-t border-slate-200 p-4">
<div className="flex items-center justify-between">
<div className="flex items-center gap-3">
<div className="w-9 h-9 bg-gradient-to-br from-slate-200 to-slate-300 rounded-full flex items-center justify-center">
<span className="text-slate-700 font-semibold text-sm">
{user?.full_name?.charAt(0) || 'U'}
</span>
</div>
<div className="flex-1 min-w-0">
<p className="font-medium text-slate-900 text-sm truncate">
{user?.full_name || 'Usuario'}
</p>
<p className="text-xs text-slate-500 truncate">{user?.email}</p>
</div>
</div>
<button
onClick={() => logout()}
className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
title="Cerrar Sesión"
>
<LogOut className="w-4 h-4 text-slate-600" />
</button>
</div>
</SidebarFooter>
</Sidebar>

<main className="flex-1 flex flex-col">
<header className="bg-white border-b border-slate-200 px-6 py-4 lg:hidden">
<div className="flex items-center gap-4">
<SidebarTrigger className="hover:bg-slate-100 p-2 rounded-lg transition-colors" />
<img src="/logo.jpeg" alt="Master Partes" className="h-8 w-auto object-contain" />
</div>
</header>

<div className="flex-1 overflow-auto">
{children}
</div>
</main>
</div>
</SidebarProvider>
);
}