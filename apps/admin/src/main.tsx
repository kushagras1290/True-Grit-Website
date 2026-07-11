import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router";

import "./styles/app.css";
import { Shell } from "./components/layout";
import { EmptyState } from "./components/ui";
import { CategoryEditorPage, CategoryListPage } from "./features/categories";
import { DashboardPage } from "./features/dashboard";
import { AuditPage, InventoryPage, MediaPage, OrdersPage, UsersPage } from "./features/operations";
import { ProductEditorPage, ProductListPage } from "./features/products";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Shell />}>
            <Route index element={<DashboardPage />} />
            <Route path="products" element={<ProductListPage />} />
            <Route path="products/:id" element={<ProductEditorPage />} />
            <Route path="categories" element={<CategoryListPage />} />
            <Route path="categories/:id" element={<CategoryEditorPage />} />
            <Route path="inventory" element={<InventoryPage />} />
            <Route path="orders" element={<OrdersPage />} />
            <Route path="media" element={<MediaPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="audit" element={<AuditPage />} />
            <Route
              path="*"
              element={<EmptyState title="Page not found" hint="Use the navigation to get back." />}
            />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
