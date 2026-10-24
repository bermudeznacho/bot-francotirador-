import os
import ccxt
import pandas as pd
import urllib.parse
import urllib.request

# =====================================================================
# 0. INTERRUPTOR DE PRUEBA TELEGRAM
# =====================================================================
# Pon esto en False después de recibir el primer mensaje para que no te 
# bombardee cada 20 minutos.
ENVIAR_SALUDO_INICIAL = False 

# =====================================================================
# 1. NOTIFICACIONES TELEGRAM
# =====================================================================
def notificar_telegram(mensaje):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        return 
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    datos = urllib.parse.urlencode({'chat_id': chat_id, 'text': mensaje}).encode('utf-8')
    
    try:
        peticion = urllib.request.Request(url, data=datos)
        urllib.request.urlopen(peticion)
    except Exception as e:
        print(f"No se pudo enviar el mensaje a Telegram: {e}")

# =====================================================================
# 2. CONEXIÓN OFICIAL A BITVAVO
# =====================================================================
OPERATOR_ID = 1001  

exchange = ccxt.bitvavo({
    'apiKey': os.environ.get('BITVAVO_API_KEY'),
    'secret': os.environ.get('BITVAVO_SECRET_KEY'),
    'enableRateLimit': True,
    'options': {'operatorId': OPERATOR_ID},
})

MONEDA_BASE = 'EUR'
RIESGO_PORCENTAJE = 0.02  
TEMPORALIDAD = '2h'
MINIMO_ORDEN_EUR = 5.5    

# =====================================================================
# 3. MATRIZ MULTI-MOTOR DE CRIPTOMONEDAS
# =====================================================================
CONFIG_MONEDAS = {
    'SOL/EUR': {'activo': True, 'donchian': 20, 'vol_mult': 1.5, 'atr_mult': 2.35, 'usar_adx': False, 'adx_min': 20},
    'ETH/EUR': {'activo': True, 'donchian': 20, 'vol_mult': 1.5, 'atr_mult': 2.35, 'usar_adx': False, 'adx_min': 20},
    'SUI/EUR': {'activo': True, 'donchian': 20, 'vol_mult': 1.5, 'atr_mult': 2.35, 'usar_adx': False, 'adx_min': 20},
    'PEPE/EUR': {'activo': True, 'donchian': 7, 'vol_mult': 2.3, 'atr_mult': 2.65, 'usar_adx': False, 'adx_min': 20},
    'AAVE/EUR': {'activo': True, 'donchian': 25, 'vol_mult': 1.5, 'atr_mult': 1.35, 'usar_adx': False, 'adx_min': 20},
    'SEI/EUR': {'activo': True, 'donchian': 7, 'vol_mult': 1.7, 'atr_mult': 2.60, 'usar_adx': False, 'adx_min': 20},
    'STX/EUR': {'activo': True, 'donchian': 22, 'vol_mult': 1.7, 'atr_mult': 1.85, 'usar_adx': False, 'adx_min': 20},
}

# =====================================================================
# 4. MOTOR MATEMÁTICO EXACTO DE TRADINGVIEW
# =====================================================================
def calcular_indicadores(df, cfg):
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['vol_ma'] = df['volume'].rolling(20).mean()
    df['max_canal'] = df['high'].shift(1).rolling(cfg['donchian']).max()
    
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - df['close'].shift(1)).abs()
    tr3 = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = tr.ewm(alpha=1/14, adjust=False).mean()
    
    up = df['high'].diff()
    down = -df['low'].diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    plus_di = 100 * (plus_dm.ewm(alpha=1/14, adjust=False).mean() / df['atr'])
    minus_di = 100 * (minus_dm.ewm(alpha=1/14, adjust=False).mean() / df['atr'])
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).fillna(0)
    df['adx'] = dx.ewm(alpha=1/14, adjust=False).mean()
    
    return df

# =====================================================================
# 5. MEMORIA DEL BOT: MAXIMO DESDE COMPRA
# =====================================================================
def obtener_maximo_desde_compra(par, df):
    try:
        mis_compras = exchange.fetch_my_trades(par, limit=5)
        compras = [t for t in mis_compras if t['side'] == 'buy']
        if compras:
            ts_ultima_compra = compras[-1]['timestamp']
            velas_desde_compra = df[df['timestamp'] >= (ts_ultima_compra - 7200000)]
            if not velas_desde_compra.empty:
                return float(velas_desde_compra['high'].max())
    except Exception:
        pass
    return float(df['high'].iloc[-2:].max())

# =====================================================================
# 6. CALCULAR EL VALOR TOTAL Y EL RIESGO
# =====================================================================
def obtener_capital_y_riesgo(balance):
    eur_total = float(balance['total'].get(MONEDA_BASE, 0.0))
    for par in CONFIG_MONEDAS.keys():
        moneda = par.split('/')[0]
        cantidad = float(balance['total'].get(moneda, 0.0))
        if cantidad > 0:
            try:
                precio = float(exchange.fetch_ticker(par)['last'])
                eur_total += (cantidad * precio)
            except Exception:
                pass
    riesgo_1r = eur_total * RIESGO_PORCENTAJE
    return eur_total, riesgo_1r

# =====================================================================
# 7. EJECUCIÓN PRINCIPAL
# =====================================================================
def ejecutar_francotirador():
    exchange.load_markets()
    balance = exchange.fetch_balance()
    capital_total, riesgo_1r = obtener_capital_y_riesgo(balance)
    eur_libre = float(balance['free'].get(MONEDA_BASE, 0.0))
    
    if ENVIAR_SALUDO_INICIAL:
        notificar_telegram(f"🤖 ¡Test Completado! El Bot Francotirador está conectado.\n\nCapital Total: {capital_total:.2f} €\nSaldo Libre: {eur_libre:.2f} €\nRiesgo ajustado por disparo: {riesgo_1r:.2f} €\n\n(Recuerda poner ENVIAR_SALUDO_INICIAL = False en GitHub para no recibir esto cada 20 min).")
    
    for par, cfg in CONFIG_MONEDAS.items():
        if not cfg['activo']:
            continue
            
        try:
            moneda = par.split('/')[0]
            cantidad_actual = float(balance['free'].get(moneda, 0.0))
            precio_actual = float(exchange.fetch_ticker(par)['last'])
            valor_posicion_eur = cantidad_actual * precio_actual
            
            bars = exchange.fetch_ohlcv(par, timeframe=TEMPORALIDAD, limit=250)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df = calcular_indicadores(df, cfg)
            
            v = df.iloc[-2]
            distancia_stop = float(v['atr'] * cfg['atr_mult'])
            
            # --- VENDER (TRAILING STOP) ---
            if valor_posicion_eur >= MINIMO_ORDEN_EUR:
                maximo_alcanzado = obtener_maximo_desde_compra(par, df)
                stop_movil_amarillo = maximo_alcanzado - distancia_stop
                
                if precio_actual <= stop_movil_amarillo:
                    # 1. Recuperar precio de compra para calcular beneficio
                    precio_compra = 0.0
                    try:
                        mis_compras = [t for t in exchange.fetch_my_trades(par, limit=5) if t['side'] == 'buy']
                        if mis_compras:
                            precio_compra = float(mis_compras[-1]['price'])
                    except Exception:
                        pass
                    
                    # 2. Calcular Rendimiento
                    pnl_texto = ""
                    if precio_compra > 0:
                        rendimiento_pct = ((precio_actual - precio_compra) / precio_compra) * 100
                        beneficio_eur = (precio_actual * cantidad_actual) - (precio_compra * cantidad_actual)
                        icono = "🟢 GANANCIA" if beneficio_eur > 0 else "🔴 PÉRDIDA CORTADA"
                        pnl_texto = f"\n{icono}: {beneficio_eur:.2f} € ({rendimiento_pct:.2f}%)\nPrecio de compra: {precio_compra} €"

                    # 3. Ejecutar venta
                    qty_vender = float(exchange.amount_to_precision(par, cantidad_actual))
                    exchange.create_order(par, 'market', 'sell', qty_vender, None, {'operatorId': OPERATOR_ID})
                    
                    # 4. Enviar notificación
                    notificar_telegram(f"🎯 VENTA EJECUTADA\nMoneda: {par}\nPrecio de salida: {precio_actual} €{pnl_texto}")
            
            # --- COMPRAR (DISPARO) ---
            else:
                hay_gasolina = v['volume'] > (v['vol_ma'] * cfg['vol_mult'])
                hay_tendencia_adx = (not cfg['usar_adx']) or (v['adx'] > cfg['adx_min'])
                
                disparo_largo = (v['close'] > v['ema200'] and v['close'] > v['max_canal'] and hay_gasolina and hay_tendencia_adx)
                
                if disparo_largo:
                    qty_calculada = riesgo_1r / distancia_stop
                    coste_eur = qty_calculada * precio_actual
                    
                    if coste_eur > (eur_libre * 0.98):
                        qty_calculada = (eur_libre * 0.98) / precio_actual
                        coste_eur = qty_calculada * precio_actual
                        
                    if coste_eur >= MINIMO_ORDEN_EUR:
                        qty_compra = float(exchange.amount_to_precision(par, qty_calculada))
                        stop_inicial = precio_actual - distancia_stop
                        
                        exchange.create_order(par, 'market', 'buy', qty_compra, None, {'operatorId': OPERATOR_ID})
                        eur_libre -= coste_eur
                        
                        notificar_telegram(f"🚀 COMPRA FRANCOTIRADOR\nMoneda: {par}\nInversión: {coste_eur:.2f} €\nPrecio de entrada: {precio_actual} €\nStop Loss Inicial: {stop_inicial:.4f} €")
                    
        except Exception as e:
            print(f"❌ Error procesando {par}: {e}")

if __name__ == "__main__":
    ejecutar_francotirador()
