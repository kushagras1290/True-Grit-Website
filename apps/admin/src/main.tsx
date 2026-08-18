import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router";

import "./styles/app.css";
import { AdminErrorBoundary } from "./components/error-boundary";
import { Shell } from "./components/layout";
import { ToastProvider } from "./components/toast";
import { AdminLocaleProvider } from "./lib/i18n";
import { EmptyState } from "./components/ui";
import { AccountPage } from "./features/account";
import { AppearancePage } from "./features/appearance";
import { ArchivePage } from "./features/archive";
import { ArticleEditorPage, ArticleListPage } from "./features/articles";
import { AnalyticsPage } from "./features/analytics";
import { AdminLoginPage, AdminResetPasswordPage, RequireAdminAuth } from "./features/auth";
import { BundlesListPage } from "./features/bundles";
import { CategoryEditorPage, CategoryListPage } from "./features/categories";
import { CurrencyRatesPage } from "./features/currency-rates";
import { DiscussionDetailPage, DiscussionsListPage } from "./features/community";
import { ContentCommentsPage } from "./features/content-comments";
import { DashboardPage } from "./features/dashboard";
import { DbBrowserPage } from "./features/db-browser";
import { EmailControlPage } from "./features/email-control";
import { FarmRequestDetailPage, FarmRequestsListPage } from "./features/farm-requests";
import { ExpandedCommercePage } from "./features/expanded-commerce";
import { GiftCardsListPage } from "./features/gift-cards";
import { HomepageSettingsPage } from "./features/homepage-settings";
import { ImageGuidePage } from "./features/image-guide";
import { MessagesPage } from "./features/messages";
import { SupportBotSettingsPage } from "./features/support-bot-settings";
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
import { PriceAdjustmentsPage } from "./features/price-adjustments";
import { ProductEditorPage, ProductListPage } from "./features/products";
import { PromotionsListPage } from "./features/promotions";
import { RecipeEditorPage, RecipeListPage } from "./features/recipes";
import { ReportsPage } from "./features/reports";
import { RefundsOversightPage } from "./features/refunds";
import { FarmRevenueDetailPage, RevenuePage } from "./features/revenue";
import { ReturnDetailPage, ReturnsListPage } from "./features/returns";
import { ReviewsListPage } from "./features/reviews";
import { ScopeManagementPage } from "./features/scopes";
import { AdminLogsPage } from "./features/server-logs";
import { SiteControlPage } from "./features/site-control";
import { SubmissionDetailPage, SubmissionsListPage } from "./features/submissions";
import { SubscriptionsListPage } from "./features/subscriptions";
import { TagsCertificationsPage } from "./features/tags-certifications";
import { RequireSuperAdmin } from "./lib/permissions";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

/** Resets the crash screen on navigation: `key={pathname}` remounts the
 *  boundary, so clicking to a different page recovers without a reload. */
function RouteErrorBoundary({ children }: { children: ReactNode }) {
  const location = useLocation();
  return <AdminErrorBoundary key={location.pathname}>{children}</AdminErrorBoundary>;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AdminLocaleProvider>
        <ToastProvider>
          <BrowserRouter>
            <RouteErrorBoundary>
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
                  <Route path="analytics" element={<AnalyticsPage />} />
                  <Route path="messages" element={<MessagesPage />} />
                  <Route path="products" element={<ProductListPage />} />
                  <Route path="products/:id" element={<ProductEditorPage />} />
                  <Route path="categories" element={<CategoryListPage />} />
                  <Route path="categories/:id" element={<CategoryEditorPage />} />
                  <Route path="tags-certifications" element={<TagsCertificationsPage />} />
                  <Route path="price-adjustments" element={<PriceAdjustmentsPage />} />
                  <Route path="currency-rates" element={<CurrencyRatesPage />} />
                  <Route path="promotions" element={<PromotionsListPage />} />
                  <Route path="gift-cards" element={<GiftCardsListPage />} />
                  <Route path="bundles" element={<BundlesListPage />} />
                  <Route path="subscriptions" element={<SubscriptionsListPage />} />
                  <Route path="expanded-commerce" element={<ExpandedCommercePage />} />
                  <Route path="inventory" element={<InventoryPage />} />
                  <Route path="farms" element={<FarmsPage />} />
                  <Route path="farm-requests" element={<FarmRequestsListPage />} />
                  <Route path="farm-requests/:id" element={<FarmRequestDetailPage />} />
                  <Route path="orders" element={<OrdersPage />} />
                  <Route path="orders/:id" element={<OrderDetailPage />} />
                  <Route path="returns" element={<ReturnsListPage />} />
                  <Route path="returns/:id" element={<ReturnDetailPage />} />
                  <Route path="refunds" element={<RefundsOversightPage />} />
                  <Route path="revenue" element={<RevenuePage />} />
                  <Route path="revenue/:farmId" element={<FarmRevenueDetailPage />} />
                  <Route path="archive" element={<ArchivePage />} />
                  <Route path="homepage-settings" element={<HomepageSettingsPage />} />
                  <Route path="appearance" element={<AppearancePage />} />
                  <Route path="site-control" element={<SiteControlPage />} />
                  <Route path="email" element={<EmailControlPage />} />
                  {/* The homepage controls used to live under Site Control; keep
                  bookmarks and links from older docs working. */}
                  <Route
                    path="site-control/homepage"
                    element={<Navigate to="/homepage-settings" replace />}
                  />
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
                  <Route path="content-comments" element={<ContentCommentsPage />} />
                  <Route path="reviews" element={<ReviewsListPage />} />
                  <Route path="contact-attempts" element={<ContactAttemptsPage />} />
                  <Route path="users" element={<UsersPage />} />
                  <Route path="scopes" element={<ScopeManagementPage />} />
                  <Route path="audit" element={<AuditPage />} />
                  <Route path="reports" element={<ReportsPage />} />
                  <Route path="help-assistant" element={<SupportBotSettingsPage />} />
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
            </RouteErrorBoundary>
          </BrowserRouter>
        </ToastProvider>
      </AdminLocaleProvider>
    </QueryClientProvider>
  </StrictMode>,
);
