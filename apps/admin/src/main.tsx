import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router";

import "./styles/app.css";
import { Shell } from "./components/layout";
import { ToastProvider } from "./components/toast";
import { EmptyState } from "./components/ui";
import { AccountPage } from "./features/account";
import { AdminLoginPage, AdminResetPasswordPage, RequireAdminAuth } from "./features/auth";
import { CategoryEditorPage, CategoryListPage } from "./features/categories";
import { DashboardPage } from "./features/dashboard";
import {
  AuditPage,
  FarmsPage,
  InventoryPage,
  MediaPage,
  OrderDetailPage,
  OrdersPage,
  UsersPage,
} from "./features/operations";
import { ProductEditorPage, ProductListPage } from "./features/products";
import { SiteControlPage } from "./features/site-control";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route path="login" element={<AdminLoginPage />} />
            <Route path="reset-password" element={<AdminResetPasswordPage />} />
            <Route
              element={
                <RequireAdminAuth>
                  <Shell />
                </RequireAdminAuth>
              }
            >
              <Route index element={<DashboardPage />} />
              <Route path="products" element={<ProductListPage />} />
              <Route path="products/:id" element={<ProductEditorPage />} />
              <Route path="categories" element={<CategoryListPage />} />
              <Route path="categories/:id" element={<CategoryEditorPage />} />
              <Route path="inventory" element={<InventoryPage />} />
              <Route path="farms" element={<FarmsPage />} />
              <Route path="orders" element={<OrdersPage />} />
              <Route path="orders/:id" element={<OrderDetailPage />} />
              <Route path="site-control" element={<SiteControlPage />} />
              <Route path="media" element={<MediaPage />} />
              <Route path="users" element={<UsersPage />} />
              <Route path="audit" element={<AuditPage />} />
              <Route path="account" element={<AccountPage />} />
              <Route
                path="*"
                element={
                  <EmptyState title="Page not found" hint="Use the navigation to get back." />
                }
              />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  </StrictMode>,
);
