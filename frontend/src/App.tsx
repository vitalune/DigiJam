import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { SessionProvider } from './context/SessionContext';
import { HomePage } from './components/pages/HomePage';
import { ConfigPage } from './components/pages/ConfigPage';
import { InstructionsPage } from './components/pages/InstructionsPage';
import { RecordingPage } from './components/pages/RecordingPage';
import { ProcessingPage } from './components/pages/ProcessingPage';
import { VocalsPage } from './components/pages/VocalsPage';
import { FinalProcessingPage } from './components/pages/FinalProcessingPage';

function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/configure" element={<ConfigPage />} />
          <Route path="/instructions" element={<InstructionsPage />} />
          <Route path="/recording" element={<RecordingPage />} />
          <Route path="/processing" element={<ProcessingPage />} />
          <Route path="/vocals" element={<VocalsPage />} />
          <Route path="/final-processing" element={<FinalProcessingPage />} />
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  );
}

export default App;
