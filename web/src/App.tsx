import { Route, Routes } from "react-router-dom";
import Console from "./pages/Console";
import Home from "./pages/Home";
import Play from "./pages/Play";
import Tv from "./pages/Tv";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/tv" element={<Tv />} />
      <Route path="/play/:room" element={<Play />} />
      <Route path="/console" element={<Console />} />
      <Route path="*" element={<Home />} />
    </Routes>
  );
}
