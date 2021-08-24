using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

public class MainMenu : MonoBehaviour
{
    // Tutorial to check out: https://www.youtube.com/watch?v=zc8ac_qUXQY

    public void PlayButtonPressed()
    {
        SceneManager.LoadScene("Game");
    }

    public void QuitButtonPressed()
    {
        Debug.Log("Quitting application");
        Application.Quit();
    }
}
