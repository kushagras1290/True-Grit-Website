import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";

import "./styles/app.css";
import { Shell } from "./components/layout";
import { ToastProvider } from "./components/toast";
import { EmptyState } from "./components/ui";
import { AccountPage } from "./features/account";
import { ArchivePage } from "./features/archive";
import { ArticleEditorPage, ArticleListPage } from "./features/articles";
import { AdminLoginPage, AdminResetPasswordPage, RequireAdminAuth } from "./features/auth";
import { CategoryEditorPage, CategoryListPage } from "./features/categories";
import { DiscussionDetailPage, DiscussionsListPage } from "./features/community";
import { DashboardPage } from "./features/dashboard";
import { DbBrowserPage } from "./features/db-browser";
import { ImageGuidePage } from "./features/image-guide";
import {
  AuditPage,
  ContactAttemptsPage,
  FarmsPage,
  InventoryPage,
  MediaPage,
  OrderDetailPage,
  OrdersPage,
  UsersPage,
} from "./features/operations";
import { ProductEditorPage, ProductListPage } from "./features/products";
import { RecipeEditorPage, RecipeListPage } from "./features/recipes";
import { ReportsPage } from "./features/reports";
import { RefundsOversightPage } from "./features/refunds";
import { FarmRevenueDetailPage, RevenuePage } from "./features/revenue";
import { ReturnDetailPage, ReturnsListPage } from "./features/returns";
import { ScopeManagementPage } from "./features/scopes";
import { AdminLogsPage } from "./features/server-logs";
import { SiteControlPage } from "./features/site-control";
import { SubmissionDetailPage, SubmissionsListPage } from "./features/submissions";
import { RequireSuperAdmin } from "./lib/permissions";

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
              <Route path="returns" element={<ReturnsListPage />} />
              <Route path="returns/:id" element={<ReturnDetailPage />} />
              <Route path="refunds" element={<RefundsOversightPage />} />
              <Route path="revenue" element={<RevenuePage />} />
              <Route path="revenue/:farmId" element={<FarmRevenueDetailPage />} />
              <Route path="archive" element={<ArchivePage />} />
              <Route path="site-control" element={<SiteControlPage />} />
              <Route path="blog" element={<ArticleListPage />} />
              <Route path="blog/:id" element={<ArticleEditorPage />} />
              <Route path="recipes" element={<RecipeListPage />} />
              <Route path="recipes/:id" element={<RecipeEditorPage />} />
              <Route path="media" element={<MediaPage />} />
              <Route path="image-guide" element={<ImageGuidePage />} />
              <Route path="submissions" element={<SubmissionsListPage />} />
              <Route path="submissions/:id" element={<SubmissionDetailPage />} />
              <Route path="community" element={<DiscussionsListPage />} />
              <Route path="community/:id" element={<DiscussionDetailPage />} />
              <Route path="contact-attempts" element={<ContactAttemptsPage />} />
              <Route path="users" element={<UsersPage />} />
              <Route path="scopes" element={<ScopeManagementPage />} />
              <Route path="audit" element={<AuditPage />} />
              <Route path="reports" element={<ReportsPage />} />
              <Route
                path="admin-logs"
                element={
                  <RequireSuperAdmin>
                    <AdminLogsPage />
                  </RequireSuperAdmin>
                }
              />
              <Route path="server-logs" element={<Navigate to="/admin-logs" replace />} />
              <Route path="db-browser" element={<DbBrowserPage />} />
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
