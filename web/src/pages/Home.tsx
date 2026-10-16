import { Link } from "react-router-dom";
import Mascot from "../components/Mascot";
import { NAME } from "../lib/brand";
import { randomRoom } from "../lib/match";

export default function Home() {
  const room = randomRoom();
  return (
    <div className="center home">
      <Mascot pose="wave" size={140} />
      <h1>{NAME}</h1>
      <p className="dim">Watch together. Call it together.</p>
      <nav>
        <Link to={`/tv?room=${room}`}>Open the TV screen</Link>
        <Link to="/console">Operator console</Link>
      </nav>
      <p className="dim small">Mock prototype · synthetic data · TV and phone must be tabs of the same browser.</p>
    </div>
  );
}
