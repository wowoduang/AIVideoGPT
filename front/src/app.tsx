import { Toaster } from '@/components/ui/sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom';
import Landing from './pages/Landing';
import Workspace from './pages/Workspace';
import AuthCallback from './pages/AuthCallback';
import AuthError from './pages/AuthError';
import LoginPage from './pages/auth/Login';
import RegisterPage from './pages/auth/Register';
import ForgotPasswordPage from './pages/auth/ForgotPassword';
import Dashboard from './pages/Dashboard';
import Projects from './pages/Projects';
import ProjectEditorLayout from './components/layout/ProjectEditorLayout';
import MaterialPage from './pages/editor/Material';
import AnalysisPage from './pages/editor/Analysis';
import DubbingPage from './pages/editor/Dubbing';
import PricingPage from './pages/static/Pricing';
import CasesPage from './pages/static/Cases';
import PrivacyPolicyPage from './pages/static/PrivacyPolicy';
import TermsOfServicePage from './pages/static/TermsOfService';
// MODULE_IMPORTS_START
// MODULE_IMPORTS_END

const queryClient = new QueryClient();

const AppRoutes = () => (
  <Routes>
    <Route path="/" element={<Landing />} />
    <Route path="/login" element={<LoginPage />} />
    <Route path="/register" element={<RegisterPage />} />
    <Route path="/forgot-password" element={<ForgotPasswordPage />} />

    <Route path="/dashboard" element={<Dashboard />} />
    <Route path="/projects" element={<Projects />} />
    <Route path="/projects/:id" element={<ProjectEditorLayout />}>
      <Route index element={<Navigate to="material" replace />} />
      <Route path="material" element={<MaterialPage />} />
      <Route path="analysis" element={<AnalysisPage />} />
      <Route path="dubbing" element={<DubbingPage />} />
    </Route>

    <Route path="/pricing" element={<PricingPage />} />
    <Route path="/cases" element={<CasesPage />} />
    <Route path="/privacy-policy" element={<PrivacyPolicyPage />} />
    <Route path="/terms-of-service" element={<TermsOfServicePage />} />

    <Route path="/workspace" element={<Workspace />} />
    <Route path="/auth/callback" element={<AuthCallback />} />
    <Route path="/auth/error" element={<AuthError />} />

    <Route path="*" element={<Navigate to="/" replace />} />
    {/* MODULE_ROUTES_START */}
    {/* MODULE_ROUTES_END */}
  </Routes>
);

const App = () => (
  <QueryClientProvider client={queryClient}>
    {/* MODULE_PROVIDERS_START */}
    {/* MODULE_PROVIDERS_END */}
    <TooltipProvider>
      <Toaster />
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </TooltipProvider>
    {/* MODULE_PROVIDERS_CLOSE */}
  </QueryClientProvider>
);

export default App;
export { AppRoutes };
