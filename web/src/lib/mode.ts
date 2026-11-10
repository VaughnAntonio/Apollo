/** True in the public build (VITE_MODE=static), which reads a snapshot instead of the local API. */
export const isStatic = () => import.meta.env.VITE_MODE === 'static'
