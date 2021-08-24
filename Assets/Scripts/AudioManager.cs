using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Audio;

/*
    TUTORIAL ------------------------------------------------------------------

    In Unity's inspector, audio clips are provided to the AudioManager prefab.

    To play a sound from the code, call the AudioManager singleton methods to
    play sounds immediately or to queue them for sequential playing.

    SAMPLE CODE ---------------------------------------------------------------

    // Get singleton instance
    AudioManager audioManager = AudioManager.GetInstance();

    // Immediately plays the clip named "BeerBeer"
    audioManager.Play("BeerBeer");

    // Immediately plays one of the three provided clips
    audioManager.PlayRandom("Burp1", "Burp2", "Burp3");

    // Immediately plays the first sound queued, and starts the next when the
    // first is done
    // WARNING: if a clip's `loop` property is checked, the queue will never finish
    audioManager.Queue("MainThemeIntro", "MainThemeLoop");

    // Clears the queue and stops the sound currently playing
    audioManager.ClearQueue();

    // All the methods above can be chained (builder-pattern)
    audioManager.ClearQueue().Queue("SongIntro", "SongLoop").Play("Fart");
*/

public class AudioManager : MonoBehaviour
{
    public Sound[] sounds;

    private static AudioManager instance;
    private Queue<Sound> soundQueue;
    private Sound soundCurrentlyPlaying;

    public static AudioManager GetInstance()
    {
        return instance;
    }

    void Awake()
    {
        // Prefab/Singleton check
        if(instance != null && instance != this)
        {
            Destroy(this.gameObject);
        }
        else
        {
            instance = this;
        }

        // Initialize clips provided in Inspector
        foreach(Sound sound in sounds)
        {
            // Assign an AudioSource to the Sound object
            sound.source = gameObject.AddComponent<AudioSource>();

            // Configure the AudioSource
            sound.source.clip = sound.clip;
            sound.source.volume = sound.volume;
            sound.source.loop = sound.loop;
        }
    }

    public AudioManager Play(string name)
    {
        Sound soundToPlay = FindSound(name);
        if (soundToPlay != null)
        {
            soundToPlay.Play();
        }
        return instance;
    }

    public AudioManager PlayRandom(params string[] names)
    {
        System.Random random = new System.Random();
        int selected = random.Next(0, names.Length);
        Play(names[selected]);
        return instance;
    }

    public AudioManager Queue(params string[] names)
    {
        foreach(string name in names)
        {
            Sound soundToQueue = FindSound(name);
            if (soundToQueue != null)
            {
                QueueSound(soundToQueue);
            }
        }
        return instance;
    }

    public AudioManager ClearQueue()
    {
        soundQueue.Clear();
        if(soundCurrentlyPlaying != null
        && soundCurrentlyPlaying.isPlaying)
        {
            soundCurrentlyPlaying.Stop();
        }
        return instance;
    }

    // Private ----------------------------------------------------------------

    private void QueueSound(Sound sound)
    {
        soundQueue.Enqueue(sound);
        if(soundCurrentlyPlaying == null)
        {
            PlayQueue();
        }
    }

    private void PlayQueue()
    {
        // Check if there is something left to play
        if(soundQueue.Count == 0)
        {
            soundCurrentlyPlaying = null;
            return;
        }

        // Pop and play a sound
        soundCurrentlyPlaying = soundQueue.Dequeue();
        soundCurrentlyPlaying.Play();

        // Monitor the end of the clip
        // WARNING: this will never happen if the sound is looping
        StartCoroutine(PlayNextSound());
    }

    private IEnumerator PlayNextSound()
    {
        yield return new WaitUntil(() => soundCurrentlyPlaying.isPlaying == false);
        PlayQueue();
    }

    private Sound FindSound(string name)
    {
        // Retrieve sound from array if it exists
        Sound soundToPlay = Array.Find(sounds, sound => sound.name == name);
        if(soundToPlay == null)
        {
            Debug.LogWarning("Sound " + name + " has not been provided to AudioManager!");
        }
        return soundToPlay;
    }
}
