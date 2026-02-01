import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { HomePage } from './components/pages/HomePage';
import { ConfigPage } from './components/pages/ConfigPage';
import { InstructionsPage } from './components/pages/InstructionsPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/configure" element={<ConfigPage />} />
        <Route path="/instructions" element={<InstructionsPage />} />
        {/* Future pages will be added here */}
        <Route path="/recording" element={<div>Recording Page - Coming Soon</div>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
