import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { HomePage } from './components/pages/HomePage';
import { ConfigPage } from './components/pages/ConfigPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/configure" element={<ConfigPage />} />
        {/* Future pages will be added here */}
        <Route path="/instructions" element={<div>Instructions Page - Coming Soon</div>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
