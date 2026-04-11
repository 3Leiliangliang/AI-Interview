<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  isTyping: { type: Boolean, default: false },
  showPassword: { type: Boolean, default: false },
  passwordLength: { type: Number, default: 0 }
})

const purpleRef = ref(null)
const blackRef = ref(null)
const orangeRef = ref(null)
const yellowRef = ref(null)

const purplePos = ref({ faceX: 0, faceY: 0, bodySkew: 0 })
const blackPos = ref({ faceX: 0, faceY: 0, bodySkew: 0 })
const orangePos = ref({ faceX: 0, faceY: 0, bodySkew: 0 })
const yellowPos = ref({ faceX: 0, faceY: 0, bodySkew: 0 })

const isPurpleBlinking = ref(false)
const isBlackBlinking = ref(false)
const isLookingAtEachOther = ref(false)
const isPurplePeeking = ref(false)

const timers = []

const clamp = (value, min, max) => Math.max(min, Math.min(max, value))
const isHidingPassword = computed(() => props.passwordLength > 0 && !props.showPassword)

const addTimer = (id) => {
  timers.push(id)
  return id
}

const clearAllTimers = () => {
  while (timers.length) {
    clearTimeout(timers.pop())
  }
}

const calcPos = (el, mouseX, mouseY) => {
  if (!el) return { faceX: 0, faceY: 0, bodySkew: 0 }
  const rect = el.getBoundingClientRect()
  const centerX = rect.left + rect.width / 2
  const centerY = rect.top + rect.height / 3
  const deltaX = mouseX - centerX
  const deltaY = mouseY - centerY
  return {
    faceX: clamp(deltaX / 20, -15, 15),
    faceY: clamp(deltaY / 30, -10, 10),
    bodySkew: clamp(-deltaX / 120, -6, 6)
  }
}

const handleMouseMove = (e) => {
  const { clientX, clientY } = e
  purplePos.value = calcPos(purpleRef.value, clientX, clientY)
  blackPos.value = calcPos(blackRef.value, clientX, clientY)
  orangePos.value = calcPos(orangeRef.value, clientX, clientY)
  yellowPos.value = calcPos(yellowRef.value, clientX, clientY)
}

const startBlink = (targetRef) => {
  const run = () => {
    const delay = Math.random() * 4000 + 3000
    addTimer(
      setTimeout(() => {
        targetRef.value = true
        addTimer(
          setTimeout(() => {
            targetRef.value = false
            run()
          }, 150)
        )
      }, delay)
    )
  }
  run()
}

onMounted(() => {
  window.addEventListener('mousemove', handleMouseMove)
  startBlink(isPurpleBlinking)
  startBlink(isBlackBlinking)
})

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', handleMouseMove)
  clearAllTimers()
})

watch(
  () => props.isTyping,
  (typing) => {
    if (!typing) {
      isLookingAtEachOther.value = false
      return
    }
    isLookingAtEachOther.value = true
    addTimer(
      setTimeout(() => {
        isLookingAtEachOther.value = false
      }, 800)
    )
  }
)

let peekLoopToken = 0
watch(
  () => [props.passwordLength, props.showPassword],
  ([len, visible]) => {
    peekLoopToken += 1
    const loopId = peekLoopToken
    isPurplePeeking.value = false
    if (!(len > 0 && visible)) return

    const schedule = () => {
      if (loopId !== peekLoopToken) return
      addTimer(
        setTimeout(() => {
          if (loopId !== peekLoopToken) return
          isPurplePeeking.value = true
          addTimer(
            setTimeout(() => {
              if (loopId !== peekLoopToken) return
              isPurplePeeking.value = false
              schedule()
            }, 800)
          )
        }, Math.random() * 3000 + 2000)
      )
    }
    schedule()
  },
  { immediate: true }
)

const purpleForce = computed(() => {
  if (props.passwordLength > 0 && props.showPassword) {
    return { x: isPurplePeeking.value ? 4 : -4, y: isPurplePeeking.value ? 5 : -4 }
  }
  if (isLookingAtEachOther.value) return { x: 3, y: 4 }
  return { x: purplePos.value.faceX * 0.16, y: purplePos.value.faceY * 0.16 }
})

const blackForce = computed(() => {
  if (props.passwordLength > 0 && props.showPassword) return { x: -4, y: -4 }
  if (isLookingAtEachOther.value) return { x: 0, y: -4 }
  return { x: blackPos.value.faceX * 0.15, y: blackPos.value.faceY * 0.15 }
})

const pupilFollow = (position) => ({ transform: `translate(${position.x}px, ${position.y}px)` })
</script>

<template>
  <div class="scene">
    <div
      ref="purpleRef"
      class="char purple"
      :style="{
        height: props.isTyping || isHidingPassword ? '440px' : '400px',
        transform:
          props.passwordLength > 0 && props.showPassword
            ? 'skewX(0deg)'
            : props.isTyping || isHidingPassword
              ? `skewX(${purplePos.bodySkew - 12}deg) translateX(40px)`
              : `skewX(${purplePos.bodySkew}deg)`
      }"
    >
      <div
        class="eyes purple-eyes"
        :style="{
          left:
            props.passwordLength > 0 && props.showPassword
              ? '20px'
              : isLookingAtEachOther
                ? '55px'
                : `${45 + purplePos.faceX}px`,
          top:
            props.passwordLength > 0 && props.showPassword
              ? '35px'
              : isLookingAtEachOther
                ? '65px'
                : `${40 + purplePos.faceY}px`
        }"
      >
        <div class="eye" :class="{ blink: isPurpleBlinking }">
          <div class="pupil" :style="pupilFollow(purpleForce)" />
        </div>
        <div class="eye" :class="{ blink: isPurpleBlinking }">
          <div class="pupil" :style="pupilFollow(purpleForce)" />
        </div>
      </div>
    </div>

    <div
      ref="blackRef"
      class="char black"
      :style="{
        transform:
          props.passwordLength > 0 && props.showPassword
            ? 'skewX(0deg)'
            : isLookingAtEachOther
              ? `skewX(${blackPos.bodySkew * 1.5 + 10}deg) translateX(20px)`
              : props.isTyping || isHidingPassword
                ? `skewX(${blackPos.bodySkew * 1.5}deg)`
                : `skewX(${blackPos.bodySkew}deg)`
      }"
    >
      <div
        class="eyes black-eyes"
        :style="{
          left:
            props.passwordLength > 0 && props.showPassword
              ? '10px'
              : isLookingAtEachOther
                ? '32px'
                : `${26 + blackPos.faceX}px`,
          top:
            props.passwordLength > 0 && props.showPassword
              ? '28px'
              : isLookingAtEachOther
                ? '12px'
                : `${32 + blackPos.faceY}px`
        }"
      >
        <div class="eye small" :class="{ blink: isBlackBlinking }">
          <div class="pupil tiny" :style="pupilFollow(blackForce)" />
        </div>
        <div class="eye small" :class="{ blink: isBlackBlinking }">
          <div class="pupil tiny" :style="pupilFollow(blackForce)" />
        </div>
      </div>
    </div>

    <div
      ref="orangeRef"
      class="char orange"
      :style="{
        transform:
          props.passwordLength > 0 && props.showPassword
            ? 'skewX(0deg)'
            : `skewX(${orangePos.bodySkew}deg)`
      }"
    >
      <div
        class="eyes plain"
        :style="{
          left:
            props.passwordLength > 0 && props.showPassword
              ? '50px'
              : `${82 + orangePos.faceX}px`,
          top:
            props.passwordLength > 0 && props.showPassword
              ? '85px'
              : `${90 + orangePos.faceY}px`
        }"
      >
        <div class="dot" />
        <div class="dot" />
      </div>
    </div>

    <div
      ref="yellowRef"
      class="char yellow"
      :style="{
        transform:
          props.passwordLength > 0 && props.showPassword
            ? 'skewX(0deg)'
            : `skewX(${yellowPos.bodySkew}deg)`
      }"
    >
      <div
        class="eyes plain yellow-eyes"
        :style="{
          left:
            props.passwordLength > 0 && props.showPassword
              ? '20px'
              : `${52 + yellowPos.faceX}px`,
          top:
            props.passwordLength > 0 && props.showPassword
              ? '35px'
              : `${40 + yellowPos.faceY}px`
        }"
      >
        <div class="dot" />
        <div class="dot" />
      </div>
      <div
        class="mouth"
        :style="{
          left:
            props.passwordLength > 0 && props.showPassword
              ? '10px'
              : `${40 + yellowPos.faceX}px`,
          top:
            props.passwordLength > 0 && props.showPassword
              ? '88px'
              : `${88 + yellowPos.faceY}px`
        }"
      />
    </div>
  </div>
</template>

<style scoped>
.scene {
  position: relative;
  width: 550px;
  height: 400px;
}

.char {
  position: absolute;
  bottom: 0;
  transition: all 0.7s ease-in-out;
  transform-origin: bottom center;
}

.purple {
  left: 70px;
  width: 180px;
  background: #6c3ff5;
  border-radius: 10px 10px 0 0;
  z-index: 1;
}

.black {
  left: 240px;
  width: 120px;
  height: 310px;
  background: #2d2d2d;
  border-radius: 8px 8px 0 0;
  z-index: 2;
}

.orange {
  left: 0;
  width: 240px;
  height: 200px;
  background: #ff9b6b;
  border-radius: 120px 120px 0 0;
  z-index: 3;
}

.yellow {
  left: 310px;
  width: 140px;
  height: 230px;
  background: #e8d754;
  border-radius: 70px 70px 0 0;
  z-index: 4;
}

.eyes {
  position: absolute;
  display: flex;
  transition: all 0.2s ease-out;
}

.purple-eyes {
  gap: 8px;
}

.black-eyes {
  gap: 6px;
}

.eye {
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: #ffffff;
  display: grid;
  place-items: center;
  transition: all 0.15s ease;
  overflow: hidden;
}

.eye.small {
  width: 16px;
  height: 16px;
}

.eye.blink {
  height: 2px;
}

.eye.blink .pupil {
  opacity: 0;
}

.pupil {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #2d2d2d;
  transition: transform 0.1s ease-out;
}

.pupil.tiny {
  width: 6px;
  height: 6px;
}

.plain {
  gap: 8px;
}

.yellow-eyes {
  gap: 6px;
}

.dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: #2d2d2d;
}

.mouth {
  position: absolute;
  width: 80px;
  height: 4px;
  border-radius: 999px;
  background: #2d2d2d;
  transition: all 0.2s ease-out;
}

@media (max-width: 1150px) {
  .scene {
    transform: scale(0.9);
    transform-origin: center bottom;
  }
}
</style>
