import { Provider } from "react-redux";
import { store } from "@/app/store";
import { Dashboard } from "@/app/Dashboard";

export function App() {
  return (
    <Provider store={store}>
      <Dashboard />
    </Provider>
  );
}
