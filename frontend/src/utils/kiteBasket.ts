/**
 * Zerodha Kite Basket JSON Exporter for AURA-NSE Pro.
 *
 * Generates official Kite Basket JSON schema compatible with Zerodha Kite Web
 * (Orders -> Baskets -> Import JSON).
 */

export interface KiteBasketItem {
  variety: string;
  tradingsymbol: string;
  exchange: string;
  transaction_type: "BUY" | "SELL";
  order_type: "LIMIT" | "MARKET" | "SL" | "SL-M";
  product: "CNC" | "MIS" | "NRML";
  quantity: number;
  price: number;
  trigger_price: number;
  tag?: string;
}

export function formatKiteBasket(predictions: any[]): KiteBasketItem[] {
  return predictions.map((p) => {
    const cleanSymbol = p.symbol.replace(".NS", "").replace(".BO", "");
    return {
      variety: "regular",
      tradingsymbol: cleanSymbol,
      exchange: "NSE",
      transaction_type: "BUY",
      order_type: "LIMIT",
      product: "CNC", // Delivery trade for swing positions
      quantity: Number(p.quantity) || 1,
      price: Number(p.entry_price) || 0,
      trigger_price: 0,
      tag: "AURA_SWING",
    };
  });
}

export function downloadKiteBasketJson(predictions: any[], filename?: string): void {
  // Section 18.2: Basket export strictly disabled on demo data
  const hasDemo = predictions.some(
    (p) => p.is_demo === true || p.audit_hash?.startsWith("demo_") || (p.id >= 100 && p.id <= 105)
  );
  if (hasDemo) {
    alert("Kite Basket Export Disabled: Demo data cannot be exported to broker orders. Connect live local backend for real entered trades.");
    return;
  }

  const basket = formatKiteBasket(predictions);
  const jsonStr = JSON.stringify(basket, null, 2);
  const blob = new Blob([jsonStr], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const todayStr = new Date().toISOString().split("T")[0];

  a.href = url;
  a.download = filename || `AURA_Kite_Basket_${todayStr}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
