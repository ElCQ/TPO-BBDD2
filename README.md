# TPO-BBDD2

1.  Agregar Usuario: crear un nuevo documento en MongoDB con los datos del usuario. idUser, Nombre, Apellido, DNI, Username, Password, Active, Fecha Alta, Categorización (Low, Medium, Top), TarjetasGuardadas -> Numero Tarjeta. Guarda log en Cassandra. Devolver últimos 5 movimientos (logs) del usuario. LOW (> 10 compras) | MEDIUM (10 < X < 20) | TOP (>20 compras)
2.  Log In: chequear contra MongoDB user y password. Si no valida, 401 y guarda log en cassandra. Si valida, guardar idusuario y username:
    Estructura REDIS
    hash:username -> idUser | username | carrito [{producto:x, cantidad:y},{producto:a, cantidad:b}]. Guardar log de inicio de sesión en cassandra.
3.  Log Out: Romper hash de REDIS. Guardar log en cassandra con la lista del carrito de compras.
4.  Agregar producto a Carrito: agregar {producto:x, cantidad:y} a lista de REDIS. Si no especifica cantidad, arranca en 1. Si el producto ya existe en la lista, se suma la cantidad. La cantidad máxima que se puede seleccionar de un producto no debe superar la cantidad de stock del mismo. Guardar log en cassandra agregarProducto [listaPreviaAccion].
5.  Eliminar producto: eliminar {producto:x, cantidad:y} a lista de REDIS. Si la cantidad de producto a eliminar llega a 0, se elimina el producto del carrito. Guardar log eliminarProducto [listaPreviaAccion]
6.  Traer historial de compras: Traer lista de idCompra | Fecha | Carrito [{producto:x, cantidad:y},{producto:a, cantidad:b}]. Guardar log cassandra.
7.  Replicar Carrito: a partir de un idCompra, pisar el carrito actual con el carrito de la compra seleccionada. La función debería de fallar si alguno de los productos no tiene stock, mencionando cual. Guardar log
8.  ConvertirResumen: Validar Stock. Si no, tirá error. Si si, agregar nuevo documento en MongoDB Ventas -> idVenta | idUser | Fecha | Carrito | TotalVenta | Forma de Pago (null) | PagoCompleto (False). Devuelve idVenta | TotalVenta | Fecha | Descuentos | Impuestos | DatosCliente. Guarda Log Cassandra.
9.  BuscarTajertas: Para un userID, devuelve la lista de trarjeta guardadas del usuario.
10. Seleccionar Método de Pago: (Opciones: Efectivo, MP, Tarjeta). Si es tarjeta, escribir numero de tarjeta. Dentro del request tiene que estar la opcion de guardar el numero de tarjeta en TarjetasGuardadas del usuario. Guardar Log
11. Comprar: Validar stock. Si no, tirá error. Si si, descuenta stock en MongoDB Productos. Buscar documento en MongoDB Ventas por idVenta -> cambiar PagoCompleto (True) y actualizar MétodoPago. Log Cassandra con el Carrito
12. Validar Stock: A partir de una lista de productos y cantidades, validar contra MongoDB Productos.
13. AgregarProductoCatálogo: Agregar nuevo producto a MongoDB Productos -> idProducto | Nombre | Descripción | Precio | Foto (URL) | Stock. Guardar Log Cassandra
14. ActualizarProducto: A partir de un idProducto, actualziar los datos. Guardar Log
15. Eliminar Producto: A partir de un idProducto, eliminar el producto. Guardar Log
16. LogProductos: Devuelve lista de actividades de producto asociadas a la tabla de actividades de producto.

log in [USER]
log out [USER]
registrar [USER]
eliminar [USER]
agregarProducto (tabién incluye aumentar la cantidad) [USER] Y [PRODUCTO]
eliminarProducto (también incluye reducir la cantidad) [USER] Y [PRODUCTO]
traerHistorial [USER]
ReplicarCarrito [USER]
ConvertirResumen [USER]
Compra [USER]
ActualizarProducto [PRODUCTO]

ESTRCUTURAS:

CREATE TABLE user_activity_log (
user_id TEXT, -- Identificador único del usuario
event_time TIMESTAMP, -- Hora del evento
event_type TEXT, -- Tipo de evento (ej. "eliminar producto", "realizar compra", etc.)
carrito TEXT,  
 PRIMARY KEY (user_id, event_time)
) WITH CLUSTERING ORDER BY (event_time DESC);

CREATE TABLE stock_activity_log (
user_id TEXT,
product_id TEXT, -- Identificador único del producto
event_time TIMESTAMP, -- Hora del evento
event_type TEXT, -- Tipo de evento (ej. "agregar producto", "quitar producto")
producto TEXT, -- JSON CON LOS DATOS DEL PRODUCTO ANTES DE SER REALIZADA LA ACCIÓN
PRIMARY KEY (product_id, event_time)
) WITH CLUSTERING ORDER BY (event_time DESC);
