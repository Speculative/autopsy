import { mount } from 'svelte'
import './app.css'
import App from './App.svelte'
import { initStudyTracking } from './studyEvents'

initStudyTracking()

const app = mount(App, {
  target: document.getElementById('app')!,
})

export default app
