import { BrowserRouter, Routes, Route } from "react-router-dom";
import UploadPage from "./pages/UploadPage";
import ReportPage from "./pages/ReportPage";
import DailyChallenge from "./pages/DailyChallenge";
import ParamsLab from "./pages/ParamsLab";
import "./App.css";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/report" element={<ReportPage />} />
        <Route path="/challenge" element={<DailyChallenge />} />
        <Route path="/params" element={<ParamsLab />} />
      </Routes>
    </BrowserRouter>
  );
}
