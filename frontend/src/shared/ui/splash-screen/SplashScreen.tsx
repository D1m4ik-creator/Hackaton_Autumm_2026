import { motion, useReducedMotion } from 'framer-motion'
import { AezaLogo } from '../aeza-logo/AezaLogo'
import './splash-screen.css'

export function SplashScreen() {
  const shouldReduceMotion = useReducedMotion()

  return (
    <motion.div
      className="app-splash"
      role="status"
      aria-live="polite"
      aria-label="Загрузка"
      initial={shouldReduceMotion ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={shouldReduceMotion ? undefined : { opacity: 0 }}
      transition={{ duration: shouldReduceMotion ? 0 : 0.4, ease: 'easeInOut' }}
    >
      <AezaLogo className="app-splash__logo" />
    </motion.div>
  )
}
