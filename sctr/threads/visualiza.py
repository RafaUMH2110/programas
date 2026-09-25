import pandas as pd
import matplotlib.pyplot as plt

# Cargar datos
df = pd.read_csv('datos_simulacion.csv')

# Gráficas
fig, axs = plt.subplots(2, 1, figsize=(10, 8))

# 1. Altura vs Setpoint
axs[0].plot(df['tiempo'], df['altura'], label='Altura (h)', color='blue')
axs[0].plot(df['tiempo'], df['setpoint'], label='Setpoint (SP)', color='red', linestyle='--')
axs[0].set_title('Respuesta del Nivel del Tanque')
axs[0].set_xlabel('Tiempo (s)')
axs[0].set_ylabel('Altura (m)')
axs[0].grid(True)
axs[0].legend()

# 2. Error vs Tiempo
axs[1].plot(df['tiempo'], df['error'], label='Error (e)', color='green')
axs[1].axhline(0, color='black', linewidth=1)
axs[1].set_title('Error de Control')
axs[1].set_xlabel('Tiempo (s)')
axs[1].set_ylabel('Error (m)')
axs[1].grid(True)
axs[1].legend()

plt.tight_layout()
plt.show()

# Métricas rápidas
print(f"Error máximo absoluto: {abs(df['error']).max():.4f} m")
print(f"Valor final de altura: {df['altura'].iloc[-1]:.4f} m")