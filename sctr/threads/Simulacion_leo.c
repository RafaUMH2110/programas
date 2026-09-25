/**
 * simulacion_control_proceso.c
 * 
 * Simulación en tiempo real de un tanque de líquido con control PID.
 * Implementado con pthreads para separar procesos:
 * 1. Hilo de Proceso (Plantilla): Simula la dinámica física del tanque.
 * 2. Hilo de Control: Calcula la acción del PID y actualiza la válvula.
 * 3. Hilo Principal: Maneja la entrada de usuario y el ciclo de tiempo global.
 * 
 * Autor: Leo (asistente de Rafa)
 * Contexto: Control de Procesos y Sistemas
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>
#include <math.h>
#include <time.h>
#include <signal.h>

// --- Constantes y Configuración Global ---

// Estado del sistema (compartido entre hilos)
typedef struct {
    double altura_actual;       // h(t) en metros
    double setpoint;            // SP deseado en metros
    double flujo_entrada;       // q_in (0.0 a 1.0, normalizado)
    double flujo_salida;        // q_out calculado
    double error;               // e(t) = SP - h(t)
    double error_integral;      // Suma de errores
    double error_anterior;      // e(t-1)
    
    // Parámetros PID
    double Kp, Ki, Kd;
    
    // Parámetros Físicos del Tanque
    double area_tanque;         // A en m^2
    double coef_salida;         // k para q_out = k * sqrt(h)
    double max_altura;          // Límite físico
    
    // Control de Simulación
    int ejecutando;             // Bandera de control
    double periodo_muestreo;    // Ts en segundos
    double tiempo_simulacion;   // Duración total
    double tiempo_transcurrido;
} EstadoSistema;

// Variables globales para el estado
EstadoSistema estado;
pthread_mutex_t lock_estado = PTHREAD_MUTEX_INITIALIZER;
pthread_cond_t cond_muestreo = PTHREAD_COND_INITIALIZER;

// --- Funciones de Utilidad ---

// Función para obtener tiempo absoluto para el condicional
void obtener_tiempo_absoluto(struct timespec *ts, double segundos) {
    struct timespec ahora;
    clock_gettime(CLOCK_REALTIME, &ahora);
    ts->tv_sec = ahora.tv_sec + (time_t)segundos;
    ts->tv_nsec = ahora.tv_nsec;
}

// --- Modelos Matemáticos ---

/**
 * Calcula el flujo de salida basado en la altura (Torricelli simplificado)
 * q_out = k * sqrt(h)
 */
double calcular_flujo_salida(double altura) {
    if (altura < 0) altura = 0;
    return estado.coef_salida * sqrt(altura);
}

/**
 * Calcula la acción de control PID discreto
 * u(t) = Kp*e(t) + Ki*sum(e) + Kd*(e(t)-e(t-1))/Ts
 * Se limita entre 0.0 y 1.0 (porcentaje de apertura de válvula)
 */
double calcular_control_pid() {
    double error = estado.setpoint - estado.altura_actual;
    estado.error = error;
    
    // Integral con anti-windup básico (no integrar si la válvula está saturada)
    if (estado.flujo_entrada > 0.0 && estado.flujo_entrada < 1.0) {
        estado.error_integral += error * estado.periodo_muestreo;
    }
    
    // Derivativa
    double derivada = (error - estado.error_anterior) / estado.periodo_muestreo;
    
    double salida = (estado.Kp * error) + 
                    (estado.Ki * estado.error_integral) + 
                    (estado.Kd * derivada);
    
    // Saturación
    if (salida > 1.0) salida = 1.0;
    if (salida < 0.0) salida = 0.0;
    
    estado.flujo_entrada = salida;
    estado.error_anterior = error;
    
    return salida;
}

/**
 * Actualiza el estado del tanque (Euler Forward)
 * dh/dt = (q_in - q_out) / A
 * h(t+1) = h(t) + Ts * (q_in - q_out) / A
 */
void actualizar_proceso_fisico() {
    // 1. Calcular flujo de salida actual
    estado.flujo_salida = calcular_flujo_salida(estado.altura_actual);
    
    // 2. Calcular derivada de la altura
    // q_in es un porcentaje, lo escalamos a un flujo real (ej: 0 a 0.1 m3/s)
    double flujo_real_entrada = estado.flujo_entrada * 0.1; 
    double flujo_real_salida = estado.flujo_salida * 0.05; // Ajuste para estabilidad
    
    double derivada_h = (flujo_real_entrada - flujo_real_salida) / estado.area_tanque;
    
    // 3. Integrar (Euler)
    estado.altura_actual += derivada_h * estado.periodo_muestreo;
    
    // 4. Limites físicos
    if (estado.altura_actual < 0) estado.altura_actual = 0;
    if (estado.altura_actual > estado.max_altura) estado.altura_actual = estado.max_altura;
}

// --- Hilos (Threads) ---

/**
 * Hilo del Proceso Físico
 * Simula la dinámica del tanque. Se ejecuta en el mismo periodo de muestreo.
 */
void* hilo_proceso(void* arg) {
    (void)arg;
    
    while (estado.ejecutando) {
        // Esperar señal de muestreo
        struct timespec ts;
        obtener_tiempo_absoluto(&ts, estado.periodo_muestreo);
        
        pthread_mutex_lock(&lock_estado);
        // Espera condicional con tiempo
        pthread_cond_timedwait(&cond_muestreo, &lock_estado, &ts);
        
        // Actualizar física
        actualizar_proceso_fisico();
        pthread_mutex_unlock(&lock_estado);
    }
    return NULL;
}

/**
 * Hilo del Controlador
 * Lee el estado, calcula el PID y actualiza la válvula.
 */
void* hilo_controlador(void* arg) {
    (void)arg;
    
    while (estado.ejecutando) {
        struct timespec ts;
        obtener_tiempo_absoluto(&ts, estado.periodo_muestreo);
        
        pthread_mutex_lock(&lock_estado);
        pthread_cond_timedwait(&cond_muestreo, &lock_estado, &ts);
        
        // Calcular nueva acción de control
        calcular_control_pid();
        
        // Imprimir estado para monitoreo (en un sistema real, esto iría a una SCADA)
        printf("\r[Sim] t=%.2fs | h=%.3fm | SP=%.3fm | q_in=%.2f | q_out=%.2f | e=%.3f", 
               estado.tiempo_transcurrido, 
               estado.altura_actual, 
               estado.setpoint, 
               estado.flujo_entrada, 
               estado.flujo_salida, 
               estado.error);
        fflush(stdout);
        
        pthread_mutex_unlock(&lock_estado);
    }
    return NULL;
}

// --- Función Principal ---

int main() {
    printf("=== Simulación de Control de Proceso: Tanque de Líquido ===\n");
    printf("Implementado con pthreads para tiempo real (simulado).\n\n");
    
    // 1. Entrada de Parámetros
    printf("Ingrese el tiempo total de simulación (segundos): ");
    if (scanf("%lf", &estado.tiempo_simulacion) != 1) return 1;
    
    printf("Ingrese el periodo de muestreo (Ts en segundos, ej: 0.1): ");
    if (scanf("%lf", &estado.periodo_muestreo) != 1) return 1;
    
    printf("Ingrese el Setpoint (altura deseada en metros): ");
    if (scanf("%lf", &estado.setpoint) != 1) return 1;
    
    // Parámetros del Tanque
    estado.area_tanque = 1.0; // m^2
    estado.coef_salida = 0.5; // k
    estado.max_altura = 2.0;  // m
    estado.altura_actual = 0.0; // Empieza vacío
    
    // Parámetros PID (ajustables)
    printf("\n--- Configuración PID ---\n");
    printf("Kp (Proporcional): "); scanf("%lf", &estado.Kp);
    printf("Ki (Integral): "); scanf("%lf", &estado.Ki);
    printf("Kd (Derivativo): "); scanf("%lf", &estado.Kd);
    
    // Inicializar errores
    estado.error = 0;
    estado.error_integral = 0;
    estado.error_anterior = 0;
    estado.ejecutando = 1;
    estado.tiempo_transcurrido = 0.0;

    // 2. Creación de Hilos
    pthread_t thread_proceso, thread_control;
    
    printf("\nIniciando simulación en tiempo real...\n");
    printf("Presione Ctrl+C para detener.\n\n");
    
    // Crear hilos (se unen al final o se dejan correr mientras main vigila)
    // Nota: En una implementación estricta, el hilo principal también podría ser el de tiempo.
    // Aquí usamos el hilo principal para el bucle de tiempo global.
    
    if (pthread_create(&thread_proceso, NULL, hilo_proceso, NULL) != 0) {
        perror("Error creando hilo proceso");
        return 1;
    }
    if (pthread_create(&thread_control, NULL, hilo_controlador, NULL) != 0) {
        perror("Error creando hilo control");
        return 1;
    }
    
    // 3. Bucle Principal de Tiempo
    // El hilo principal actúa como el "reloj" que despierta a los otros hilos
    struct timespec start_time, current_time;
    clock_gettime(CLOCK_MONOTONIC, &start_time);
    
    while (estado.ejecutando) {
        clock_gettime(CLOCK_MONOTONIC, &current_time);
        double elapsed = (current_time.tv_sec - start_time.tv_sec) + 
                         (current_time.tv_nsec - start_time.tv_nsec) / 1e9;
        
        estado.tiempo_transcurrido = elapsed;
        
        // Verificar tiempo de simulación
        if (elapsed >= estado.tiempo_simulacion) {
            estado.ejecutando = 0;
            break;
        }
        
        // Despertar a los hilos de proceso y control
        // Nota: En un sistema real de tiempo duro, esto se haría con timers de hardware.
        // Aquí usamos el condicional para sincronizar la ejecución.
        pthread_mutex_lock(&lock_estado);
        pthread_cond_broadcast(&cond_muestreo); // Despierta a ambos hilos
        pthread_mutex_unlock(&lock_estado);
        
        // Pequeña pausa para no saturar la CPU entre muestreos
        // El tiempo real se gestiona por el periodo de muestreo en los hilos
        usleep((unsigned long)(estado.periodo_muestreo * 1000000));
    }
    
    printf("\n\nSimulación finalizada.\n");
    
    // 4. Limpieza
    estado.ejecutando = 0;
    pthread_join(thread_proceso, NULL);
    pthread_join(thread_control, NULL);
    
    printf("Estado final: Altura = %.3f m\n", estado.altura_actual);
    
    return 0;
}