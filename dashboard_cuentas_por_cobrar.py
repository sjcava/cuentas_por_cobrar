import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import re

# Configuración de la página
st.set_page_config(
    page_title="Dashboard Cuentas por Cobrar - Locatel",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Colores de Locatel
COLORS = {
    'yellow': '#FED519',
    'orange': '#F79617',
    'light_green': '#7CC141',
    'medium_green': '#419E46',
    'dark_green': '#0A9561'
}

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #0A9561 0%, #419E46 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }

    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        text-align: center;
        border-left: 4px solid #0A9561;
    }

    .alert-danger {
        background: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }

    .alert-success {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_and_process_data(file_path):
    """Cargar y procesar datos del CSV"""
    try:
        # Leer archivo CSV
        df = pd.read_csv(file_path, sep=';', encoding='latin-1')

        # Limpiar nombres de columnas
        df.columns = df.columns.str.strip()

        # Limpiar datos
        df['Fecha de documento'] = df['Fecha de documento'].str.strip()
        df['Texto'] = df['Texto'].str.strip()
        df['Importe valorado ML2'] = df['Importe valorado ML2'].str.strip()
        df['Importe valorado ML2'] = df['Importe valorado ML2'].str.replace(',', '.')

        # Filtrar filas válidas
        df = df[df['Importe valorado ML2'] != '']
        df = df[df['Importe valorado ML2'].notna()]

        # Convertir a numérico
        df['Importe valorado ML2'] = pd.to_numeric(df['Importe valorado ML2'], errors='coerce')
        df = df.dropna(subset=['Importe valorado ML2'])

        # Filtrar solo valores positivos
        df_positivos = df[df['Importe valorado ML2'] > 0].copy()

        # Convertir fechas
        def parse_date(date_str):
            try:
                return pd.to_datetime(date_str, format='%d/%m/%y')
            except:
                try:
                    return pd.to_datetime(date_str, format='%d/%m/%Y')
                except:
                    return None

        df_positivos['Fecha'] = df_positivos['Fecha de documento'].apply(parse_date)
        df_positivos = df_positivos.dropna(subset=['Fecha'])

        # Calcular días de antigüedad
        today = datetime.now()
        df_positivos['Dias_Antiguedad'] = (today - df_positivos['Fecha']).dt.days

        # Extraer nombres de clientes
        def extract_client_name(text):
            text = str(text).upper()
            patterns_to_remove = [
                r'SALDO FAV PAG D FT \d+',
                r'FT \d+',
                r'\(.*?\)',
                r'TARJ\. CREDIT COMISION',
                r'CORPORACION CARD'
            ]

            for pattern in patterns_to_remove:
                text = re.sub(pattern, '', text)

            text = ' '.join(text.split())
            return text.strip()

        df_positivos['Cliente'] = df_positivos['Texto'].apply(extract_client_name)

        # Categorizar antigüedad
        def categorize_aging(days):
            if days <= 30:
                return '0-30 días'
            elif days <= 60:
                return '31-60 días'
            elif days <= 90:
                return '61-90 días'
            else:
                return 'Más de 90 días'

        df_positivos['Categoria_Antiguedad'] = df_positivos['Dias_Antiguedad'].apply(categorize_aging)

        # Categorizar riesgo
        def categorize_risk(days, amount):
            if days > 90 and amount > 50:
                return 'Alto'
            elif days > 60 or amount > 100:
                return 'Medio'
            else:
                return 'Bajo'

        df_positivos['Riesgo'] = df_positivos.apply(
            lambda x: categorize_risk(x['Dias_Antiguedad'], x['Importe valorado ML2']), axis=1
        )

        return df_positivos

    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return None

def calculate_metrics(df):
    """Calcular métricas principales"""
    if df is None or df.empty:
        return {}

    return {
        'total_facturas': len(df),
        'monto_total': df['Importe valorado ML2'].sum(),
        'clientes_unicos': df['Cliente'].nunique(),
        'promedio_factura': df['Importe valorado ML2'].mean(),
        'promedio_dias': df['Dias_Antiguedad'].mean()
    }

def create_aging_chart(df):
    """Crear gráfico de antigüedad"""
    aging_data = df.groupby('Categoria_Antiguedad')['Importe valorado ML2'].sum().reset_index()

    fig = px.pie(
        aging_data, 
        values='Importe valorado ML2', 
        names='Categoria_Antiguedad',
        title="Distribución por Antigüedad",
        color_discrete_sequence=[COLORS['dark_green'], COLORS['medium_green'], COLORS['orange'], '#dc3545']
    )

    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(height=400)

    return fig

def create_risk_chart(df):
    """Crear gráfico de riesgo"""
    risk_data = df.groupby('Riesgo')['Importe valorado ML2'].sum().reset_index()

    fig = px.bar(
        risk_data,
        x='Riesgo',
        y='Importe valorado ML2',
        title="Análisis de Riesgo",
        color='Riesgo',
        color_discrete_map={'Alto': '#dc3545', 'Medio': COLORS['orange'], 'Bajo': COLORS['light_green']}
    )

    fig.update_layout(height=400, showlegend=False)
    fig.update_traces(texttemplate='$%{y:,.0f}', textposition='outside')

    return fig

def create_clients_chart(df):
    """Crear gráfico de top clientes"""
    top_clients = df.groupby('Cliente')['Importe valorado ML2'].sum().sort_values(ascending=False).head(10)

    fig = px.bar(
        x=top_clients.values,
        y=top_clients.index,
        orientation='h',
        title="Top 10 Clientes por Monto",
        labels={'x': 'Monto ($)', 'y': 'Cliente'}
    )

    fig.update_traces(marker_color=COLORS['medium_green'])
    fig.update_layout(height=500)

    return fig

# Función principal
def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>📊 Dashboard Cuentas por Cobrar - Locatel</h1>
        <p>Análisis actualizado - Julio 2025</p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar para cargar archivo
    st.sidebar.header("📁 Cargar Datos")
    uploaded_file = st.sidebar.file_uploader(
        "Selecciona el archivo CSV",
        type=['csv'],
        help="Sube tu archivo de cuentas por cobrar en formato CSV"
    )

    # Si no hay archivo, usar datos por defecto
    if uploaded_file is None:
        st.sidebar.info("💡 Usando datos de ejemplo. Sube tu archivo CSV para análisis personalizado.")
        # Aquí podrías cargar un archivo por defecto
        df = None
    else:
        df = load_and_process_data(uploaded_file)

    # Si tenemos datos, mostrar dashboard
    if df is not None and not df.empty:
        # Calcular métricas
        metrics = calculate_metrics(df)

        # Pestañas principales
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Resumen", "⏰ Antigüedad", "👥 Top Clientes", "⚠️ Análisis de Riesgo"])

        with tab1:
            st.header("Métricas Principales")

            # Métricas en columnas
            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.metric("Total Facturas", f"{metrics['total_facturas']:,}")

            with col2:
                st.metric("Monto Total", f"${metrics['monto_total']:,.2f}")

            with col3:
                st.metric("Clientes Únicos", f"{metrics['clientes_unicos']:,}")

            with col4:
                st.metric("Promedio/Factura", f"${metrics['promedio_factura']:,.2f}")

            with col5:
                st.metric("Días Promedio", f"{metrics['promedio_dias']:.1f}")

            # Gráficos en columnas
            col1, col2 = st.columns(2)

            with col1:
                fig_aging = create_aging_chart(df)
                st.plotly_chart(fig_aging, use_container_width=True)

            with col2:
                fig_risk = create_risk_chart(df)
                st.plotly_chart(fig_risk, use_container_width=True)

        with tab2:
            st.header("Análisis de Antigüedad")

            # Tabla de antigüedad
            aging_summary = df.groupby('Categoria_Antiguedad').agg({
                'Importe valorado ML2': ['sum', 'count']
            }).round(2)

            aging_summary.columns = ['Monto Total', 'Cantidad']
            aging_summary['Porcentaje'] = (aging_summary['Monto Total'] / metrics['monto_total'] * 100).round(1)

            st.dataframe(aging_summary, use_container_width=True)

            # Gráfico de barras detallado
            aging_detail = df.groupby('Categoria_Antiguedad')['Importe valorado ML2'].sum().reset_index()
            fig_aging_detail = px.bar(
                aging_detail,
                x='Categoria_Antiguedad',
                y='Importe valorado ML2',
                title="Monto por Período de Antigüedad",
                color='Categoria_Antiguedad',
                color_discrete_sequence=[COLORS['dark_green'], COLORS['medium_green'], COLORS['orange'], '#dc3545']
            )
            fig_aging_detail.update_layout(showlegend=False)
            st.plotly_chart(fig_aging_detail, use_container_width=True)

        with tab3:
            st.header("Top Clientes")

            # Gráfico de top clientes
            fig_clients = create_clients_chart(df)
            st.plotly_chart(fig_clients, use_container_width=True)

            # Tabla de top clientes
            top_clients_table = df.groupby('Cliente')['Importe valorado ML2'].sum().sort_values(ascending=False).head(10)
            top_clients_df = pd.DataFrame({
                'Cliente': top_clients_table.index,
                'Monto Pendiente': top_clients_table.values,
                '% del Total': (top_clients_table.values / metrics['monto_total'] * 100).round(1)
            })

            st.dataframe(top_clients_df, use_container_width=True)

        with tab4:
            st.header("Análisis de Riesgo")

            # Alertas
            facturas_90_dias = len(df[df['Dias_Antiguedad'] > 90])
            if facturas_90_dias > 0:
                st.markdown(f"""
                <div class="alert-danger">
                    <strong>⚠️ Alerta Crítica:</strong> {facturas_90_dias} facturas con más de 90 días requieren atención inmediata.
                </div>
                """, unsafe_allow_html=True)

            # Métricas de riesgo
            risk_summary = df.groupby('Riesgo')['Importe valorado ML2'].sum()

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("🔴 Riesgo Alto", f"${risk_summary.get('Alto', 0):,.2f}")

            with col2:
                st.metric("🟡 Riesgo Medio", f"${risk_summary.get('Medio', 0):,.2f}")

            with col3:
                st.metric("🟢 Riesgo Bajo", f"${risk_summary.get('Bajo', 0):,.2f}")

            # Gráfico de riesgo detallado
            fig_risk_detail = create_risk_chart(df)
            st.plotly_chart(fig_risk_detail, use_container_width=True)

            # Recomendaciones
            st.markdown("""
            <div class="alert-success">
                <strong>💡 Recomendaciones:</strong>
                <ul>
                    <li>Contactar inmediatamente clientes con facturas > 90 días</li>
                    <li>Implementar recordatorios automáticos a los 45 días</li>
                    <li>Revisar términos de crédito para nuevos clientes</li>
                    <li>Considerar descuentos por pronto pago</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

            # Tabla de clientes de alto riesgo
            high_risk_clients = df[df['Riesgo'] == 'Alto'].groupby('Cliente')['Importe valorado ML2'].sum().sort_values(ascending=False)

            if not high_risk_clients.empty:
                st.subheader("🚨 Clientes de Alto Riesgo")
                st.dataframe(high_risk_clients.to_frame('Monto'), use_container_width=True)

    else:
        st.info("📁 Por favor, sube un archivo CSV para comenzar el análisis.")

        # Mostrar ejemplo de formato esperado
        st.subheader("Formato de archivo esperado:")
        example_data = pd.DataFrame({
            'Fecha de documento': ['18/2/25', '19/2/25', '22/2/25'],
            'Texto': ['CLIENTE A', 'CLIENTE B', 'CLIENTE C'],
            'Importe valorado ML2': ['27,30', '53,44', '47,86']
        })
        st.dataframe(example_data)

if __name__ == "__main__":
    main()
