import '@testing-library/jest-dom/vitest'

// jsdom doesn't implement scrollIntoView; ChatInterface calls it to auto-scroll on new messages.
window.HTMLElement.prototype.scrollIntoView = () => {}
