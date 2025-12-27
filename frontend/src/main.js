import { createApp } from 'vue'
import { createPinia } from 'pinia'
import {
    Button,
    NavBar,
    Tabbar,
    TabbarItem,
    Card,
    Tag,
    Cell,
    CellGroup,
    Icon,
    Loading,
    Empty,
    Dialog,
    Toast,
    Notify,
    PullRefresh,
    SwipeCell,
    Progress,
    Skeleton,
    Field,
    Tab,
    Tabs
} from 'vant'
import 'vant/lib/index.css'
import '@vant/touch-emulator'

import App from './App.vue'
import router from './router'
import './styles/index.css'

const app = createApp(App)

// Pinia 状态管理
app.use(createPinia())

// Vue Router
app.use(router)

// Vant 组件
app.use(Button)
app.use(NavBar)
app.use(Tabbar)
app.use(TabbarItem)
app.use(Card)
app.use(Tag)
app.use(Cell)
app.use(CellGroup)
app.use(Icon)
app.use(Loading)
app.use(Empty)
app.use(Dialog)
app.use(Toast)
app.use(Notify)
app.use(PullRefresh)
app.use(SwipeCell)
app.use(Progress)
app.use(Skeleton)
app.use(Field)
app.use(Tab)
app.use(Tabs)

app.mount('#app')

